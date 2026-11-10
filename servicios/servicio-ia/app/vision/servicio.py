"""Clasificación de imágenes y videos, y descarga del modelo para dispositivos (spec-vision.md)."""

import asyncio
import hashlib
import logging
import tempfile
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import Request

from app.comun.errores import ErrorAplicacion
from app.comun.seguridad import PREFIJO_API, UsuarioAutenticado
from app.integracion.almacen_archivos import AlmacenArchivos
from app.integracion.errores import ErrorInfraestructura
from app.integracion.repositorio_resultados import RepositorioResultadosMongo
from app.modelos.cargador import CargadorModelos, ModeloCargado
from app.modelos.esquemas import ReferenciaVersion
from app.trabajos.esquemas import Trabajo
from app.trabajos.servicio import ServicioTrabajos
from app.vision.clasificador import a_confianza, interpretar, predecir
from app.vision.esquemas import (
    Alternativa,
    ArchivoDispositivo,
    ClasificacionIncidencia,
    EtiquetaDispositivo,
    ExportacionDispositivo,
    Fotograma,
    MetadatosDispositivo,
    RespuestaClasificacion,
    ResultadoVideo,
    ResumenCategoria,
)
from app.vision.etiquetas import INDETERMINADO, etiqueta
from app.vision.imagenes import ImagenInvalida, preparar_imagen, validar_imagen
from app.vision.video import InfoVideo, VideoInvalido, extraer_fotogramas, validar_video

MODELO = "clasificador"
TIPO_TRABAJO_VIDEO = "CLASIFICACION_VIDEO"
TIEMPO_LIMITE_VIDEO = timedelta(minutes=3)
RETENCION_CLASIFICACIONES = timedelta(days=90)
CARPETA_VIDEOS = "temporales/videos"
RUTA_ARCHIVOS = f"{PREFIJO_API}/modelos/{MODELO}/dispositivo/archivos"

_logger = logging.getLogger("app.vision")


def _ahora() -> datetime:
    return datetime.now(UTC)


def _version_texto(cargado: ModeloCargado) -> str:
    return f"{MODELO}-{cargado.version.version}"


def _referencia(cargado: ModeloCargado) -> ReferenciaVersion:
    return ReferenciaVersion(nombre=MODELO, version=cargado.version.version)


def _categorias_y_umbral(cargado: ModeloCargado) -> tuple[list[str], float]:
    adicionales = cargado.version.adicionales
    return list(adicionales["etiquetas"]), float(adicionales["umbral"])


class ServicioVision:
    def __init__(
        self,
        cargador: CargadorModelos,
        resultados: RepositorioResultadosMongo,
        almacen: AlmacenArchivos,
        trabajos: ServicioTrabajos,
        reloj: Callable[[], datetime] = _ahora,
    ) -> None:
        self._cargador = cargador
        self._resultados = resultados
        self._almacen = almacen
        self._trabajos = trabajos
        self._reloj = reloj

    # --- imagen ------------------------------------------------------------------------------

    async def clasificar_imagen(
        self, datos: bytes, solicitante: UsuarioAutenticado
    ) -> RespuestaClasificacion:
        cargado = self._cargador.obtener(MODELO)
        try:
            imagen = await asyncio.to_thread(validar_imagen, datos)
        except ImagenInvalida as error:
            _logger.info("Imagen rechazada", extra={"motivo": str(error)})
            raise ErrorAplicacion(
                400, "IMAGEN_INVALIDA", "La imagen no es válida. Envíe una foto JPEG o PNG."
            ) from None
        arreglo = preparar_imagen(imagen)
        probabilidades = await asyncio.to_thread(predecir, cargado.modelo, arreglo[np.newaxis])
        categorias, umbral = _categorias_y_umbral(cargado)
        resultado = interpretar(probabilidades[0].tolist(), categorias, umbral)
        elegida = etiqueta(resultado.categoria)
        respuesta = RespuestaClasificacion(
            id=str(uuid.uuid4()),
            fecha=self._reloj(),
            categoria=resultado.categoria,
            nombre=elegida.nombre,
            cultivo=elegida.cultivo,
            tipo_incidencia_sugerido=elegida.tipo_incidencia_sugerido,
            confianza=resultado.confianza,
            alternativas=[
                Alternativa(categoria=c, nombre=etiqueta(c).nombre, confianza=p)
                for c, p in resultado.alternativas
            ],
            clasificacion=ClasificacionIncidencia(
                categoria=resultado.categoria,
                confianza=resultado.confianza,
                version_modelo=_version_texto(cargado),
            ),
            version_modelo=_referencia(cargado),
        )
        await self._guardar(respuesta, hashlib.sha256(datos).hexdigest(), solicitante)
        return respuesta

    async def _guardar(
        self, respuesta: RespuestaClasificacion, sha256: str, solicitante: UsuarioAutenticado
    ) -> None:
        documento = respuesta.model_dump(
            mode="json", by_alias=True, exclude={"aviso", "orientativo"}
        )
        documento.update(
            fecha=respuesta.fecha,
            idSolicitante=solicitante.id,
            sha256Imagen=sha256,
            fechaExpiracion=respuesta.fecha + RETENCION_CLASIFICACIONES,
        )
        try:
            await self._resultados.guardar("clasificaciones", documento)
        except ErrorInfraestructura:
            raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None

    # --- video -------------------------------------------------------------------------------

    async def solicitar_video(self, ruta_local: Path, solicitante: UsuarioAutenticado) -> Trabajo:
        try:
            await asyncio.to_thread(validar_video, ruta_local)
        except VideoInvalido as error:
            _logger.info("Video rechazado", extra={"motivo": str(error)})
            raise ErrorAplicacion(
                400, "VIDEO_INVALIDO", "El video no es válido o dura más de 60 segundos."
            ) from None
        ruta = f"{CARPETA_VIDEOS}/{uuid.uuid4()}{ruta_local.suffix.lower()}"
        try:
            datos = await asyncio.to_thread(ruta_local.read_bytes)
            await self._almacen.subir(ruta, datos, "application/octet-stream")
        except ErrorInfraestructura:
            raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None
        try:
            return await self._trabajos.crear(TIPO_TRABAJO_VIDEO, {"rutaVideo": ruta}, solicitante)
        except ErrorAplicacion:
            await self._borrar(ruta)
            raise

    async def procesar_video(self, trabajo: Trabajo) -> dict[str, Any]:
        """Manejador del trabajo `CLASIFICACION_VIDEO` (spec-trabajos.md)."""
        ruta = str(trabajo.parametros["rutaVideo"])
        try:
            datos = await self._almacen.descargar(ruta)
            if datos is None:
                raise ErrorAplicacion(
                    404,
                    "VIDEO_NO_DISPONIBLE",
                    "El video ya no está disponible. Envíelo nuevamente.",
                )
            cargado = self._cargador.obtener(MODELO)
            with tempfile.TemporaryDirectory() as carpeta:
                local = Path(carpeta) / Path(ruta).name
                local.write_bytes(datos)
                info = await asyncio.to_thread(validar_video, local)
                fotogramas = await asyncio.to_thread(extraer_fotogramas, local, info)
            lote = np.stack([f for _, f in fotogramas])
            probabilidades = await asyncio.to_thread(predecir, cargado.modelo, lote)
            resultado = agregar_video([s for s, _ in fotogramas], probabilidades, info, cargado)
            return resultado.model_dump(mode="json", by_alias=True)
        finally:
            await self._borrar(ruta)

    async def _borrar(self, ruta: str) -> None:
        try:
            await self._almacen.borrar(ruta)
        except ErrorInfraestructura:
            _logger.error("No se pudo borrar el video temporal", extra={"ruta": ruta})

    # --- dispositivos ------------------------------------------------------------------------

    def metadatos_dispositivo(self) -> MetadatosDispositivo:
        cargado = self._cargador.obtener(MODELO)
        adicionales = cargado.version.adicionales
        categorias, umbral = _categorias_y_umbral(cargado)
        return MetadatosDispositivo(
            version_modelo=_version_texto(cargado),
            version=cargado.version.version,
            fecha_publicacion=cargado.version.fecha_publicacion,
            umbral=Decimal(str(umbral)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            entrada=adicionales["entrada"],
            etiquetas=[
                EtiquetaDispositivo(
                    indice=i,
                    categoria=c,
                    nombre=etiqueta(c).nombre,
                    cultivo=etiqueta(c).cultivo,
                    tipo_incidencia_sugerido=etiqueta(c).tipo_incidencia_sugerido,
                )
                for i, c in enumerate(categorias)
            ],
            exportaciones={
                formato: ExportacionDispositivo(
                    archivos=[
                        ArchivoDispositivo(
                            ruta=f"{RUTA_ARCHIVOS}/{a['ruta']}",
                            tamanio=a["tamanio"],
                            sha256=a["sha256"],
                        )
                        for a in archivos
                    ]
                )
                for formato, archivos in adicionales["exportaciones"].items()
            },
        )

    def archivo_dispositivo(self, ruta: str) -> tuple[str, dict[str, Any]]:
        """Ruta completa en el bucket y descripción de un archivo exportado de la vigente."""
        cargado = self._cargador.obtener(MODELO)
        for archivos in cargado.version.adicionales["exportaciones"].values():
            for archivo in archivos:
                if archivo["ruta"] == ruta:
                    return f"{cargado.version.ruta_artefactos}/{ruta}", archivo
        raise ErrorAplicacion(
            404, "ARCHIVO_MODELO_NO_ENCONTRADO", "El archivo del modelo no existe."
        )

    async def descargar(self, ruta_bucket: str) -> bytes:
        try:
            datos = await self._almacen.descargar(ruta_bucket)
        except ErrorInfraestructura:
            raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None
        if datos is None:
            raise ErrorAplicacion(
                404, "ARCHIVO_MODELO_NO_ENCONTRADO", "El archivo del modelo no existe."
            )
        return datos


def agregar_video(
    segundos: list[float],
    probabilidades: np.ndarray[Any, Any],
    info: InfoVideo,
    cargado: ModeloCargado,
) -> ResultadoVideo:
    """Categoría predominante: mayor probabilidad promedio entre los fotogramas determinados."""
    categorias, umbral = _categorias_y_umbral(cargado)
    por_fotograma = [interpretar(p.tolist(), categorias, umbral) for p in probabilidades]
    determinados = [i for i, r in enumerate(por_fotograma) if r.categoria != INDETERMINADO]
    if determinados:
        promedio = probabilidades[determinados].mean(axis=0)
        indice = int(promedio.argmax())
        predominante, confianza = categorias[indice], a_confianza(float(promedio[indice]))
    else:
        predominante = INDETERMINADO
        confianza = a_confianza(float(probabilidades.max(axis=1).mean()))

    principales: dict[str, list[Decimal]] = defaultdict(list)
    for resultado in por_fotograma:
        principales[resultado.categoria].append(resultado.confianza)
    resumen = sorted(
        (
            ResumenCategoria(
                categoria=c,
                fotogramas_principal=len(v),
                confianza_promedio=a_confianza(float(sum(v) / len(v))),
            )
            for c, v in principales.items()
        ),
        key=lambda r: (-r.fotogramas_principal, r.categoria),
    )
    referencia = ReferenciaVersion(nombre=MODELO, version=cargado.version.version)
    return ResultadoVideo(
        categoria_predominante=predominante,
        nombre=etiqueta(predominante).nombre,
        confianza=confianza,
        clasificacion=ClasificacionIncidencia(
            categoria=predominante, confianza=confianza, version_modelo=_version_texto(cargado)
        ),
        resumen=resumen,
        fotogramas=[
            Fotograma(
                segundo=Decimal(str(s)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                categoria=r.categoria,
                confianza=r.confianza,
            )
            for s, r in zip(segundos, por_fotograma, strict=True)
        ],
        duracion_segundos=Decimal(str(info.duracion)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        version_modelo=referencia,
    )


def deserializar_keras(datos: bytes) -> Any:
    """Cargador del artefacto `modelo.keras`, con una inferencia de calentamiento."""
    import tensorflow as tf

    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "modelo.keras"
        ruta.write_bytes(datos)
        modelo = tf.keras.models.load_model(ruta, compile=False)
    modelo(np.zeros((1, 224, 224, 3), dtype=np.float32), training=False)
    return modelo


def servicio_vision(request: Request) -> ServicioVision:
    servicio: ServicioVision = request.app.state.servicio_vision
    return servicio
