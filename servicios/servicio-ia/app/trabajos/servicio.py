"""Creación y consulta de trabajos (spec-trabajos.md 2.8)."""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.comun.correlacion import id_correlacion_actual
from app.comun.errores import ErrorAplicacion
from app.comun.seguridad import PREFIJO_API, UsuarioAutenticado
from app.integracion.errores import ErrorInfraestructura
from app.integracion.rabbitmq import ConexionRabbitMq, crear_sobre
from app.integracion.repositorio_trabajos import RepositorioTrabajos
from app.trabajos.esquemas import ErrorTrabajo, RespuestaTrabajoCreado, Trabajo
from app.trabajos.estados import EstadoTrabajo, calcular_fecha_expiracion
from app.trabajos.registro import RegistroTipos

TIPO_MENSAJE = "ProcesarTrabajo"
MENSAJES_ERROR = {
    "TIEMPO_AGOTADO": "El trabajo superó el tiempo máximo de procesamiento.",
    "TRABAJO_NO_PROCESADO": "El trabajo no pudo procesarse. Intente nuevamente.",
    "COLA_NO_DISPONIBLE": "El trabajo no pudo encolarse. Intente nuevamente.",
    "ERROR_INTERNO": "Ocurrió un error inesperado.",
}

_logger = logging.getLogger("app.trabajos")


def ahora_utc() -> datetime:
    return datetime.now(UTC)


def error_trabajo(codigo: str) -> dict[str, str]:
    return ErrorTrabajo(codigo=codigo, mensaje=MENSAJES_ERROR[codigo]).model_dump()


class ServicioTrabajos:
    def __init__(
        self,
        repositorio: RepositorioTrabajos,
        conexion: ConexionRabbitMq,
        registro: RegistroTipos,
        dias_retencion: int,
        reloj: Callable[[], datetime] = ahora_utc,
    ) -> None:
        self._repositorio = repositorio
        self._conexion = conexion
        self._registro = registro
        self._dias_retencion = dias_retencion
        self._reloj = reloj

    async def crear(
        self, tipo: str, parametros: dict[str, Any], solicitante: UsuarioAutenticado
    ) -> Trabajo:
        if tipo not in self._registro:
            raise KeyError(f"Tipo de trabajo no registrado: {tipo}")
        trabajo = Trabajo(
            id=str(uuid.uuid4()),
            tipo=tipo,
            estado=EstadoTrabajo.EN_COLA,
            id_solicitante=solicitante.id,
            id_correlacion=id_correlacion_actual.get(),
            parametros=parametros,
            fecha_creacion=self._reloj(),
        )
        try:
            await self._repositorio.guardar_nuevo(trabajo.a_documento())
        except ErrorInfraestructura:
            raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None

        sobre = crear_sobre(TIPO_MENSAJE, {"idTrabajo": trabajo.id}, trabajo.id_correlacion)
        try:
            await self._conexion.publicar(self._conexion.cola_trabajos, sobre)
        except ErrorInfraestructura:
            await self._marcar_no_encolado(trabajo)
            raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None
        _logger.info("Trabajo encolado", extra={"idTrabajo": trabajo.id, "tipo": tipo})
        return trabajo

    async def _marcar_no_encolado(self, trabajo: Trabajo) -> None:
        fin = self._reloj()
        try:
            await self._repositorio.cambiar_estado(
                trabajo.id,
                EstadoTrabajo.EN_COLA,
                EstadoTrabajo.FALLIDO,
                {
                    "error": error_trabajo("COLA_NO_DISPONIBLE"),
                    "fechaFin": fin,
                    "fechaExpiracion": calcular_fecha_expiracion(fin, self._dias_retencion),
                },
            )
        except ErrorInfraestructura:
            _logger.error(
                "No se pudo marcar el trabajo no encolado", extra={"idTrabajo": trabajo.id}
            )

    async def obtener_para(self, id_trabajo: str, solicitante: UsuarioAutenticado) -> Trabajo:
        no_encontrado = ErrorAplicacion(
            404, "TRABAJO_NO_ENCONTRADO", "El trabajo solicitado no existe."
        )
        try:
            id_normalizado = str(uuid.UUID(id_trabajo))
        except ValueError:
            raise no_encontrado from None
        try:
            documento = await self._repositorio.obtener(id_normalizado)
        except ErrorInfraestructura:
            raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None
        if documento is None:
            raise no_encontrado
        trabajo = Trabajo.desde_documento(documento)
        if trabajo.id_solicitante != solicitante.id:
            raise no_encontrado
        return trabajo


def respuesta_creado(trabajo: Trabajo) -> JSONResponse:
    """`202` con el trabajo y `Location` para consultarlo (RQ-TRA-01)."""
    cuerpo = RespuestaTrabajoCreado(
        id_trabajo=trabajo.id, estado=trabajo.estado, fecha_creacion=trabajo.fecha_creacion
    )
    return JSONResponse(
        status_code=202,
        content=cuerpo.model_dump(mode="json", by_alias=True),
        headers={"Location": f"{PREFIJO_API}/trabajos/{trabajo.id}"},
    )


def servicio_trabajos(request: Request) -> ServicioTrabajos:
    """Dependencia de FastAPI para los módulos que crean trabajos."""
    servicio: ServicioTrabajos = request.app.state.servicio_trabajos
    return servicio
