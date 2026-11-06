"""Endpoints de visión y descarga del modelo para dispositivos (spec-vision.md 2.7 y 2.8).

La descarga para dispositivos vive aquí y no en `modelos/router.py`: necesita las etiquetas de
`vision/`, y `modelos` no puede importar módulos de capacidad (constitución §3).
"""

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import Depends, File, Header, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from app.comun.errores import ErrorAplicacion, respuestas_error
from app.comun.seguridad import UsuarioAutenticado, requerir_roles, router_protegido
from app.trabajos.servicio import respuesta_creado
from app.vision.esquemas import MetadatosDispositivo, RespuestaClasificacion
from app.vision.servicio import ServicioVision, servicio_vision

router_vision = router_protegido(tags=["vision"])
solo_tecnico = requerir_roles("tecnico_campo")
BLOQUE = 1024 * 1024
TIPOS_CONTENIDO = {
    ".tflite": "application/octet-stream",
    ".bin": "application/octet-stream",
    ".json": "application/json",
}
EXTENSIONES_VIDEO = {".mp4", ".mov", ".webm", ".m4v", ".mkv"}


def _demasiado_grande() -> ErrorAplicacion:
    return ErrorAplicacion(
        400, "ARCHIVO_DEMASIADO_GRANDE", "El archivo supera el tamaño máximo permitido."
    )


async def _leer_con_limite(archivo: UploadFile, limite: int) -> bytes:
    partes: list[bytes] = []
    total = 0
    while bloque := await archivo.read(BLOQUE):
        total += len(bloque)
        if total > limite:
            raise _demasiado_grande()
        partes.append(bloque)
    return b"".join(partes)


@router_vision.post(
    "/clasificaciones",
    status_code=201,
    summary="Clasificar la foto de una hoja (orientativo)",
    responses=respuestas_error(400, 401, 403, 500, 503),
)
async def clasificar_imagen(
    request: Request,
    imagen: Annotated[UploadFile, File(description="Foto JPEG o PNG de hasta 10 MB")],
    usuario: UsuarioAutenticado = Depends(solo_tecnico),
    servicio: ServicioVision = Depends(servicio_vision),
) -> RespuestaClasificacion:
    limite = int(request.app.state.configuracion.vision_tamanio_maximo_imagen_mb * BLOQUE)
    datos = await _leer_con_limite(imagen, limite)
    return await servicio.clasificar_imagen(datos, usuario)


@router_vision.post(
    "/clasificaciones/videos",
    status_code=202,
    summary="Clasificar un video corto como trabajo asíncrono",
    responses=respuestas_error(400, 401, 403, 500, 503),
)
async def clasificar_video(
    request: Request,
    video: Annotated[UploadFile, File(description="Video MP4, MOV o WebM de hasta 50 MB y 60 s")],
    usuario: UsuarioAutenticado = Depends(solo_tecnico),
    servicio: ServicioVision = Depends(servicio_vision),
) -> JSONResponse:
    limite = int(request.app.state.configuracion.vision_tamanio_maximo_video_mb * BLOQUE)
    sufijo = Path(video.filename or "").suffix.lower()
    with tempfile.TemporaryDirectory() as carpeta:
        local = Path(carpeta) / f"video{sufijo if sufijo in EXTENSIONES_VIDEO else '.mp4'}"
        total = 0
        with local.open("wb") as salida:
            while bloque := await video.read(BLOQUE):
                total += len(bloque)
                if total > limite:
                    raise _demasiado_grande()
                salida.write(bloque)
        trabajo = await servicio.solicitar_video(local, usuario)
    return respuesta_creado(trabajo)


@router_vision.get(
    "/modelos/clasificador/dispositivo",
    summary="Versión vigente del clasificador para usarlo sin conexión",
    responses=respuestas_error(400, 401, 403, 500, 503),
)
async def metadatos_dispositivo(
    _: UsuarioAutenticado = Depends(solo_tecnico),
    servicio: ServicioVision = Depends(servicio_vision),
) -> MetadatosDispositivo:
    return servicio.metadatos_dispositivo()


@router_vision.get(
    "/modelos/clasificador/dispositivo/archivos/{ruta:path}",
    summary="Descargar un archivo del modelo exportado (TFLite o TF.js)",
    responses={
        **respuestas_error(400, 401, 403, 404, 500, 503),
        304: {"description": "Sin cambios"},
    },
    response_class=Response,
)
async def archivo_dispositivo(
    ruta: str,
    si_no_coincide: Annotated[str | None, Header(alias="If-None-Match")] = None,
    _: UsuarioAutenticado = Depends(solo_tecnico),
    servicio: ServicioVision = Depends(servicio_vision),
) -> Response:
    ruta_bucket, descripcion = servicio.archivo_dispositivo(ruta)
    etag = f'"{descripcion["sha256"]}"'
    encabezados = {"ETag": etag, "Cache-Control": "private, max-age=86400"}
    if si_no_coincide and etag in {v.strip().removeprefix("W/") for v in si_no_coincide.split(",")}:
        return Response(status_code=304, headers=encabezados)
    datos = await servicio.descargar(ruta_bucket)
    tipo = TIPOS_CONTENIDO.get(Path(ruta).suffix, "application/octet-stream")
    return Response(content=datos, media_type=tipo, headers=encabezados)
