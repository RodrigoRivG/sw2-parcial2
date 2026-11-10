"""Consumidor de la cola de trabajos (spec-trabajos.md 2.9)."""

import asyncio
import contextlib
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, TypeVar

from aio_pika.abc import AbstractIncomingMessage

from app.comun.correlacion import id_correlacion_actual
from app.comun.errores import ErrorAplicacion
from app.integracion.errores import ErrorInfraestructura
from app.integracion.rabbitmq import ConexionRabbitMq
from app.integracion.repositorio_trabajos import RepositorioTrabajos
from app.trabajos.esquemas import Trabajo
from app.trabajos.estados import (
    EstadoTrabajo,
    calcular_fecha_expiracion,
    calcular_fecha_limite,
)
from app.trabajos.registro import DefinicionTipo, RegistroTipos
from app.trabajos.servicio import ahora_utc, error_trabajo

ESPERAS_REINTENTO = (1.0, 2.0, 4.0)
TAMANIO_MAXIMO_RESULTADO = 100_000

_logger = logging.getLogger("app.trabajos.consumidor")
T = TypeVar("T")
Accion = Callable[[], Awaitable[None]]


class _ResultadoDemasiadoGrande(Exception):
    pass


def registrar_falla_de_tarea(tarea: "asyncio.Task[None]") -> None:
    """Una tarea de fondo que falla no debe perderse en silencio."""
    if not tarea.cancelled() and (error := tarea.exception()) is not None:
        _logger.error(
            "La tarea de fondo terminó con error",
            extra={"tarea": tarea.get_name()},
            exc_info=error,
        )


class ConsumidorTrabajos:
    def __init__(
        self,
        repositorio: RepositorioTrabajos,
        registro: RegistroTipos,
        dias_retencion: int,
        reloj: Callable[[], datetime] = ahora_utc,
        esperar: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._repositorio = repositorio
        self._registro = registro
        self._dias_retencion = dias_retencion
        self._reloj = reloj
        self._esperar = esperar
        self._tarea: asyncio.Task[None] | None = None

    # --- ciclo de vida -------------------------------------------------------------------

    def iniciar(self, conexion: ConexionRabbitMq, prefetch: int) -> None:
        self._tarea = asyncio.create_task(self._consumir(conexion, prefetch), name="consumidor")
        self._tarea.add_done_callback(registrar_falla_de_tarea)

    async def _consumir(self, conexion: ConexionRabbitMq, prefetch: int) -> None:
        cola = await conexion.cola_de_consumo(prefetch)
        await cola.consume(self._al_recibir)
        _logger.info("Consumidor de trabajos iniciado", extra={"cola": cola.name})

    async def detener(self) -> None:
        if self._tarea is not None and not self._tarea.done():
            self._tarea.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._tarea

    async def _al_recibir(self, mensaje: AbstractIncomingMessage) -> None:
        await self.procesar(
            mensaje.body,
            confirmar=mensaje.ack,
            descartar=lambda: mensaje.reject(requeue=False),
        )

    # --- procesamiento -------------------------------------------------------------------

    async def procesar(self, cuerpo: bytes, confirmar: Accion, descartar: Accion) -> None:
        """Procesa un mensaje. `confirmar` es el `ack`; `descartar`, el `nack` a la DLQ."""
        try:
            sobre = json.loads(cuerpo)
            id_trabajo = str(uuid.UUID(str(sobre["datos"]["idTrabajo"])))
            id_correlacion = sobre.get("idCorrelacion")
        except (ValueError, KeyError, TypeError):
            _logger.error("Mensaje de trabajo no interpretable; va a la DLQ")
            await descartar()
            return

        contexto = id_correlacion_actual.set(str(id_correlacion) if id_correlacion else None)
        try:
            await self._procesar_trabajo(id_trabajo, confirmar, descartar)
        finally:
            id_correlacion_actual.reset(contexto)

    async def _procesar_trabajo(
        self, id_trabajo: str, confirmar: Accion, descartar: Accion
    ) -> None:
        try:
            documento = await self._con_reintentos(lambda: self._repositorio.obtener(id_trabajo))
        except ErrorInfraestructura:
            _logger.error(
                "MongoDB no disponible; el mensaje va a la DLQ", extra={"idTrabajo": id_trabajo}
            )
            await descartar()
            return
        if documento is None:
            _logger.error(
                "El trabajo del mensaje no existe; va a la DLQ", extra={"idTrabajo": id_trabajo}
            )
            await descartar()
            return

        trabajo = Trabajo.desde_documento(documento)
        if trabajo.estado is not EstadoTrabajo.EN_COLA:
            await confirmar()
            return

        try:
            definicion = self._registro.obtener(trabajo.tipo)
        except KeyError:
            _logger.error("Tipo de trabajo no registrado", extra={"tipo": trabajo.tipo})
            await self._cerrar(trabajo, EstadoTrabajo.EN_COLA, error_trabajo("ERROR_INTERNO"))
            await confirmar()
            return

        inicio = self._reloj()
        limite = calcular_fecha_limite(inicio, definicion.tiempo_limite)
        try:
            tomado = await self._con_reintentos(
                lambda: self._repositorio.cambiar_estado(
                    id_trabajo,
                    EstadoTrabajo.EN_COLA,
                    EstadoTrabajo.PROCESANDO,
                    {"fechaInicio": inicio, "fechaLimite": limite},
                )
            )
        except ErrorInfraestructura:
            _logger.error(
                "MongoDB no disponible; el mensaje va a la DLQ", extra={"idTrabajo": id_trabajo}
            )
            await descartar()
            return
        if not tomado:
            await confirmar()  # otro consumidor lo tomó
            return

        await confirmar()  # desde aquí el estado vive en MongoDB
        en_proceso = trabajo.model_copy(
            update={
                "estado": EstadoTrabajo.PROCESANDO,
                "fecha_inicio": inicio,
                "fecha_limite": limite,
            }
        )
        await self._ejecutar(en_proceso, definicion)

    async def _ejecutar(self, trabajo: Trabajo, definicion: DefinicionTipo) -> None:
        inicio = time.perf_counter()
        resultado: dict[str, Any] | None = None
        error: dict[str, str] | None = None
        try:
            crudo = await asyncio.wait_for(
                definicion.manejador(trabajo), definicion.tiempo_limite.total_seconds()
            )
            resultado = self._validar_resultado(crudo)
        except ErrorAplicacion as fallo:
            error = {"codigo": fallo.codigo, "mensaje": fallo.mensaje}
        except TimeoutError:
            error = error_trabajo("TIEMPO_AGOTADO")
        except Exception:
            _logger.exception("Error inesperado en el manejador", extra={"idTrabajo": trabajo.id})
            error = error_trabajo("ERROR_INTERNO")

        await self._cerrar(trabajo, EstadoTrabajo.PROCESANDO, error, resultado)
        _logger.info(
            "Trabajo terminado",
            extra={
                "idTrabajo": trabajo.id,
                "tipo": trabajo.tipo,
                "estado": "FALLIDO" if error else "COMPLETADO",
                "codigo": error["codigo"] if error else None,
                "duracionMs": round((time.perf_counter() - inicio) * 1000, 1),
            },
        )

    @staticmethod
    def _validar_resultado(crudo: dict[str, Any]) -> dict[str, Any]:
        """El resultado debe ser JSON puro y de hasta 100 KB (límite de documento de MongoDB)."""
        try:
            serializado = json.dumps(crudo, ensure_ascii=False)
        except (TypeError, ValueError):
            _logger.exception("El resultado del manejador no es JSON")
            raise
        if len(serializado.encode()) > TAMANIO_MAXIMO_RESULTADO:
            _logger.error("Resultado demasiado grande", extra={"bytes": len(serializado.encode())})
            raise _ResultadoDemasiadoGrande
        resultado: dict[str, Any] = json.loads(serializado)
        return resultado

    async def _cerrar(
        self,
        trabajo: Trabajo,
        desde: EstadoTrabajo,
        error: dict[str, str] | None,
        resultado: dict[str, Any] | None = None,
    ) -> None:
        fin = self._reloj()
        cambios: dict[str, Any] = {
            "fechaFin": fin,
            "fechaExpiracion": calcular_fecha_expiracion(fin, self._dias_retencion),
        }
        if error:
            cambios["error"] = error
            hacia = EstadoTrabajo.FALLIDO
        else:
            cambios["resultado"] = resultado
            hacia = EstadoTrabajo.COMPLETADO
        try:
            await self._con_reintentos(
                lambda: self._repositorio.cambiar_estado(trabajo.id, desde, hacia, cambios)
            )
        except ErrorInfraestructura:
            _logger.error(
                "No se pudo guardar el final del trabajo; lo cerrará la revisión periódica",
                extra={"idTrabajo": trabajo.id},
            )

    async def _con_reintentos(self, operacion: Callable[[], Awaitable[T]]) -> T:
        for espera in ESPERAS_REINTENTO:
            try:
                return await operacion()
            except ErrorInfraestructura as error:
                _logger.warning(
                    "Falla de infraestructura; se reintenta",
                    extra={"motivo": str(error), "esperaSegundos": espera},
                )
                await self._esperar(espera)
        return await operacion()
