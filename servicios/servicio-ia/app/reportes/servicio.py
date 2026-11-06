"""Reportes como trabajo `REPORTE`: solicitud, manejador, evento y descarga
(spec-reportes.md 2.8 y 2.9)."""

import asyncio
import hashlib
import logging
import re
import tempfile
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from fastapi import Request
from langgraph.errors import GraphRecursionError
from mcp import Client
from mcp.server.mcpserver import MCPServer

from app.comun.errores import ErrorAplicacion
from app.comun.seguridad import PREFIJO_API, UsuarioAutenticado
from app.integracion.almacen_archivos import AlmacenArchivos
from app.integracion.errores import ErrorInfraestructura
from app.integracion.modelo_lenguaje import ModeloLenguaje, ModeloLenguajeNoDisponible
from app.integracion.rabbitmq import crear_sobre
from app.integracion.transcriptor import (
    AudioInvalido,
    Transcriptor,
    TranscriptorNoDisponible,
    validar_audio,
)
from app.reportes.agente import MAXIMO_PASOS, EstadoReporte, construir_grafo, titulo_reporte
from app.reportes.catalogo import FUENTES
from app.reportes.esquemas import SolicitudTexto
from app.reportes.generadores import Documento, generar_pdf, generar_xlsx
from app.reportes.plan import FormatoReporte, PlanReporte, Tabla, describir_filtro, validar
from app.trabajos.esquemas import Trabajo
from app.trabajos.estados import EstadoTrabajo
from app.trabajos.servicio import ServicioTrabajos

_logger = logging.getLogger("app.reportes")
TIPO_TRABAJO = "REPORTE"
TIEMPO_LIMITE = timedelta(minutes=5)
ROL_PROGRAMADOS = "reportes_ia"
CARPETA_AUDIOS = "temporales/audios"
CARPETA_REPORTES = "reportes"
ESPERA_TRANSCRIPTOR = 120.0
FILAS_VISTA_PREVIA = 50
ESPERAS_EVENTO = (1.0, 2.0, 4.0)
RUTA_EVENTO = "ia.reporte.completado"
AVISO = (
    "El plan y el resumen los produjo un modelo de lenguaje; las cifras del resumen se "
    "verificaron contra las tablas. Las tablas son datos de los servicios sin cambios."
)
AVISO_PLAN_DADO = (
    "El resumen lo redactó un modelo de lenguaje y sus cifras se verificaron contra las "
    "tablas. Las tablas son datos de los servicios sin cambios."
)
TIPOS_CONTENIDO = {
    FormatoReporte.PDF: "application/pdf",
    FormatoReporte.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
EXTENSIONES = {FormatoReporte.PDF: "pdf", FormatoReporte.XLSX: "xlsx"}
SERVICIOS_POR_FUENTE = {
    "INVENTARIO": ("servicio-inventario",),
    "LABORES": ("servicio-operaciones", "servicio-gestion", "servicio-inventario"),
    "INCIDENCIAS": ("servicio-operaciones", "servicio-gestion"),
}
_MENSAJE_NO_DISPONIBLE = "El asistente no está disponible en este momento. Intente más tarde."


class PublicadorEventos(Protocol):
    async def publicar_evento(self, routing_key: str, sobre: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class ArchivoDescarga:
    datos: bytes
    nombre: str
    tipo_contenido: str
    sha256: str


def _modelo_no_disponible() -> ErrorAplicacion:
    return ErrorAplicacion(503, "MODELO_LENGUAJE_NO_DISPONIBLE", _MENSAJE_NO_DISPONIBLE)


def nombre_archivo(titulo: str, fecha: datetime, formato: FormatoReporte) -> str:
    sin_tildes = unicodedata.normalize("NFKD", titulo.lower())
    ascii_ = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")[:40].strip("-") or "reporte"
    return f"reporte-{slug}-{fecha.date().isoformat()}.{EXTENSIONES[formato]}"


def _servicios(plan: PlanReporte) -> list[str]:
    servicios: set[str] = set()
    for tabla in plan.tablas:
        servicios.update(SERVICIOS_POR_FUENTE.get(tabla.fuente, ("servicio-gestion",)))
    return sorted(servicios)


def _vista_previa(tabla: Tabla) -> dict[str, Any]:
    return {
        "titulo": tabla.titulo,
        "fuente": tabla.fuente,
        "columnas": [{"campo": c.nombre, "etiqueta": c.etiqueta} for c in tabla.columnas],
        "filas": tabla.filas[:FILAS_VISTA_PREVIA],
        "totalFilas": tabla.total_filas,
        "totalOrigen": tabla.total_origen,
    }


class ServicioReportes:
    def __init__(
        self,
        modelo: ModeloLenguaje,
        servidor_mcp: MCPServer,
        trabajos: ServicioTrabajos,
        almacen: AlmacenArchivos,
        eventos: PublicadorEventos,
        transcriptor: Transcriptor,
        retencion_dias: int = 7,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._modelo = modelo
        self._servidor_mcp = servidor_mcp
        self._trabajos = trabajos
        self._almacen = almacen
        self._eventos = eventos
        self._transcriptor = transcriptor
        self._retencion = timedelta(days=retencion_dias)
        self._reloj = reloj

    # --- solicitudes --------------------------------------------------------------------------

    async def solicitar(
        self, cuerpo: SolicitudTexto | PlanReporte, solicitante: UsuarioAutenticado
    ) -> Trabajo:
        origen = "PROGRAMADO" if solicitante.tiene_alguno(ROL_PROGRAMADOS) else "SOLICITADO"
        if isinstance(cuerpo, PlanReporte):
            if errores := validar(cuerpo):
                raise ErrorAplicacion(400, "DATOS_INVALIDOS", detalles=errores)
            parametros: dict[str, Any] = {
                "origen": origen,
                "plan": cuerpo.model_dump(mode="json", by_alias=True),
            }
        else:
            if not await self._modelo.disponible():
                raise _modelo_no_disponible()
            parametros = {"origen": origen, "texto": cuerpo.texto}
            if cuerpo.formatos:
                parametros["formatos"] = [f.value for f in cuerpo.formatos]
        return await self._trabajos.crear(TIPO_TRABAJO, parametros, solicitante)

    async def solicitar_voz(
        self,
        ruta_local: Path,
        formatos: list[FormatoReporte] | None,
        solicitante: UsuarioAutenticado,
    ) -> Trabajo:
        try:
            await asyncio.to_thread(validar_audio, ruta_local)
        except AudioInvalido as error:
            _logger.info("Audio rechazado", extra={"motivo": str(error)})
            raise ErrorAplicacion(
                400, "AUDIO_INVALIDO", "El audio no es válido o dura más de 2 minutos."
            ) from None
        if not await self._modelo.disponible():
            raise _modelo_no_disponible()
        ruta = f"{CARPETA_AUDIOS}/{uuid.uuid4()}{ruta_local.suffix.lower()}"
        try:
            datos = await asyncio.to_thread(ruta_local.read_bytes)
            await self._almacen.subir(ruta, datos, "application/octet-stream")
        except ErrorInfraestructura:
            raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None
        parametros: dict[str, Any] = {"origen": "SOLICITADO", "rutaAudio": ruta}
        if formatos:
            parametros["formatos"] = [f.value for f in formatos]
        try:
            return await self._trabajos.crear(TIPO_TRABAJO, parametros, solicitante)
        except ErrorAplicacion:
            await self._borrar(ruta)
            raise

    # --- manejador del trabajo ----------------------------------------------------------------

    async def procesar(self, trabajo: Trabajo) -> dict[str, Any]:
        parametros = trabajo.parametros
        transcripcion: str | None = None
        texto: str | None = parametros.get("texto")
        if ruta_audio := parametros.get("rutaAudio"):
            transcripcion = await self._transcribir(str(ruta_audio))
            texto = transcripcion

        plan_dado = "plan" in parametros
        entrada: EstadoReporte = {
            "texto": texto,
            "plan_dado": plan_dado,
            "formatos": [FormatoReporte(f) for f in parametros.get("formatos") or []] or None,
        }
        if plan_dado:
            entrada["plan"] = PlanReporte.model_validate(parametros["plan"])
        estado = await self._ejecutar(entrada)

        plan = estado["plan"]
        ahora = self._reloj()
        titulo = titulo_reporte(plan)
        advertencias = estado.get("advertencias", [])
        documento = Documento(
            titulo=titulo,
            fecha_generacion=ahora,
            tablas=estado["tablas"],
            filtros=[
                [describir_filtro(f, FUENTES[t.fuente]) for f in t.filtros] for t in plan.tablas
            ],
            solicitud=texto,
            resumen=estado.get("resumen"),
            advertencias=[a["mensaje"] for a in advertencias],
            aviso=AVISO_PLAN_DADO if plan_dado else AVISO,
            servicios=_servicios(plan),
        )
        archivos = []
        for formato in dict.fromkeys(plan.formatos):
            generar = generar_pdf if formato is FormatoReporte.PDF else generar_xlsx
            datos = await asyncio.to_thread(generar, documento)
            nombre = nombre_archivo(titulo, ahora, formato)
            try:
                await self._almacen.subir(
                    f"{CARPETA_REPORTES}/{trabajo.id}/{nombre}", datos, TIPOS_CONTENIDO[formato]
                )
            except ErrorInfraestructura:
                raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None
            archivos.append(
                {
                    "formato": formato.value,
                    "nombre": nombre,
                    "tamanio": len(datos),
                    "sha256": hashlib.sha256(datos).hexdigest(),
                    "ruta": f"{PREFIJO_API}/reportes/{trabajo.id}/archivos/{formato.value}",
                }
            )
        expiracion = ahora + self._retencion
        origen = str(parametros.get("origen", "SOLICITADO"))
        resultado = {
            "origen": origen,
            "transcripcion": transcripcion,
            "textoSolicitud": parametros.get("texto"),
            "plan": plan.model_dump(mode="json", by_alias=True),
            "titulo": titulo,
            "resumen": estado.get("resumen"),
            "cifrasOmitidas": estado.get("cifrasOmitidas", 0),
            "advertencias": advertencias,
            "tablas": [_vista_previa(t) for t in estado["tablas"]],
            "archivos": archivos,
            "fechaGeneracion": _iso(ahora),
            "fechaExpiracionArchivos": _iso(expiracion),
            "modeloLenguaje": self._modelo.nombre,
            "aviso": documento.aviso,
        }
        _logger.info(
            "Reporte generado",
            extra={
                "origen": origen,
                "fuentes": [t.fuente for t in plan.tablas],
                "filas": [t.total_filas for t in estado["tablas"]],
                "formatos": [a["formato"] for a in archivos],
            },
        )
        await self._notificar(trabajo, origen, titulo, archivos, expiracion)
        return resultado

    async def _transcribir(self, ruta: str) -> str:
        try:
            try:
                await self._transcriptor.esperar(ESPERA_TRANSCRIPTOR)
            except TranscriptorNoDisponible:
                raise ErrorAplicacion(
                    503,
                    "TRANSCRIPTOR_NO_DISPONIBLE",
                    "La transcripción de voz no está disponible en este momento.",
                ) from None
            try:
                datos = await self._almacen.descargar(ruta)
            except ErrorInfraestructura:
                raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None
            if datos is None:
                raise ErrorAplicacion(
                    503, "DEPENDENCIA_NO_DISPONIBLE", "El audio ya no está disponible."
                )
            with tempfile.TemporaryDirectory() as carpeta:
                local = Path(carpeta) / f"audio{Path(ruta).suffix}"
                await asyncio.to_thread(local.write_bytes, datos)
                transcripcion = await self._transcriptor.transcribir(local)
        finally:
            await self._borrar(ruta)  # solo queda la transcripción (constitución §4)
        if not transcripcion.texto.strip():
            raise ErrorAplicacion(422, "AUDIO_SIN_VOZ", "No se reconoció voz en el audio.")
        return transcripcion.texto

    async def _ejecutar(self, entrada: EstadoReporte) -> EstadoReporte:
        fallo: Exception | None = None
        async with Client(self._servidor_mcp) as sesion:
            grafo = construir_grafo(self._modelo, sesion, self._reloj().date())
            # Se captura dentro: desde afuera llegaría envuelta en un ExceptionGroup.
            try:
                estado: EstadoReporte = await grafo.ainvoke(
                    entrada, {"recursion_limit": MAXIMO_PASOS}
                )
            except ModeloLenguajeNoDisponible:
                fallo = _modelo_no_disponible()
            except GraphRecursionError:
                fallo = ErrorAplicacion(500, "ERROR_INTERNO")
            except ErrorAplicacion as error:
                fallo = error
        if fallo is not None:
            raise fallo
        return estado

    async def _notificar(
        self,
        trabajo: Trabajo,
        origen: str,
        titulo: str,
        archivos: list[dict[str, Any]],
        expiracion: datetime,
    ) -> None:
        datos = {
            "idTrabajo": trabajo.id,
            "idSolicitante": trabajo.id_solicitante,
            "origen": origen,
            "titulo": titulo,
            "archivos": [
                {k: a[k] for k in ("formato", "nombre", "tamanio", "ruta")} for a in archivos
            ],
            "fechaExpiracionArchivos": _iso(expiracion),
        }
        sobre = crear_sobre("ReporteCompletado", datos, trabajo.id_correlacion)
        for intento, espera in enumerate((0.0, *ESPERAS_EVENTO)):
            await asyncio.sleep(espera)
            try:
                await self._eventos.publicar_evento(RUTA_EVENTO, sobre)
                return
            except ErrorInfraestructura:
                _logger.warning("No se pudo publicar el evento", extra={"intento": intento + 1})
        if origen == "PROGRAMADO":  # n8n no se enteraría y el correo no saldría
            raise ErrorAplicacion(
                503,
                "EVENTO_NO_PUBLICADO",
                "El reporte se generó pero no se pudo notificar. Intente nuevamente.",
            )
        _logger.error("Evento de reporte no publicado", extra={"idTrabajo": trabajo.id})

    async def _borrar(self, ruta: str) -> None:
        try:
            await self._almacen.borrar(ruta)
        except ErrorInfraestructura:
            _logger.warning("No se pudo borrar el archivo temporal", extra={"ruta": ruta})

    # --- descarga -----------------------------------------------------------------------------

    async def descargar(
        self, id_trabajo: str, formato: str, solicitante: UsuarioAutenticado
    ) -> ArchivoDescarga:
        no_encontrado = ErrorAplicacion(
            404, "REPORTE_NO_ENCONTRADO", "El reporte solicitado no existe."
        )
        try:
            trabajo = await self._trabajos.obtener_para(id_trabajo, solicitante)
        except ErrorAplicacion as error:
            if error.codigo == "TRABAJO_NO_ENCONTRADO":
                raise no_encontrado from None
            raise
        if trabajo.tipo != TIPO_TRABAJO:
            raise no_encontrado
        if trabajo.estado in (EstadoTrabajo.EN_COLA, EstadoTrabajo.PROCESANDO):
            raise ErrorAplicacion(
                409, "REPORTE_EN_PROCESO", "El reporte todavía se está generando."
            )
        resultado = trabajo.resultado or {}
        archivo = next(
            (a for a in resultado.get("archivos", []) if a.get("formato") == formato.upper()),
            None,
        )
        if trabajo.estado is not EstadoTrabajo.COMPLETADO or archivo is None:
            raise no_encontrado
        expirado = ErrorAplicacion(
            404, "REPORTE_EXPIRADO", "El reporte ya no está disponible. Genérelo nuevamente."
        )
        expiracion = datetime.fromisoformat(
            str(resultado["fechaExpiracionArchivos"]).replace("Z", "+00:00")
        )
        if self._reloj() >= expiracion:
            raise expirado
        try:
            datos = await self._almacen.descargar(
                f"{CARPETA_REPORTES}/{trabajo.id}/{archivo['nombre']}"
            )
        except ErrorInfraestructura:
            raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None
        if datos is None:
            raise expirado
        return ArchivoDescarga(
            datos,
            str(archivo["nombre"]),
            TIPOS_CONTENIDO[FormatoReporte(archivo["formato"])],
            str(archivo["sha256"]),
        )


def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).isoformat().replace("+00:00", "Z")


def servicio_reportes(request: Request) -> ServicioReportes:
    servicio: ServicioReportes = request.app.state.servicio_reportes
    return servicio
