"""Endpoints de reportes (spec-reportes.md 2.10)."""

import tempfile
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import Depends, File, Form, Header, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from app.comun.errores import ErrorAplicacion, respuestas_error
from app.comun.seguridad import UsuarioAutenticado, requerir_roles, router_protegido, usuario_actual
from app.reportes.catalogo import FUENTES
from app.reportes.esquemas import CampoCatalogo, FuenteCatalogo, SolicitudReporte
from app.reportes.plan import OPERADORES_POR_TIPO, FormatoReporte
from app.reportes.servicio import ROL_PROGRAMADOS, ServicioReportes, servicio_reportes
from app.trabajos.servicio import respuesta_creado

router_reportes = router_protegido(tags=["reportes"])
gerencia_o_programados = requerir_roles("gerencia", ROL_PROGRAMADOS)
solo_gerencia = requerir_roles("gerencia")
BLOQUE = 1024 * 1024
EXTENSIONES_AUDIO = {".webm", ".ogg", ".oga", ".opus", ".wav", ".mp3"}


@router_reportes.post(
    "/reportes",
    status_code=202,
    summary="Pedir un reporte por texto o con el plan ya armado (trabajo asíncrono)",
    responses=respuestas_error(400, 401, 403, 500, 503),
)
async def solicitar(
    cuerpo: SolicitudReporte,
    usuario: UsuarioAutenticado = Depends(gerencia_o_programados),
    servicio: ServicioReportes = Depends(servicio_reportes),
) -> JSONResponse:
    return respuesta_creado(await servicio.solicitar(cuerpo, usuario))


@router_reportes.post(
    "/reportes/voz",
    status_code=202,
    summary="Pedir un reporte por voz (trabajo asíncrono)",
    responses=respuestas_error(400, 401, 403, 500, 503),
)
async def solicitar_voz(
    request: Request,
    audio: Annotated[UploadFile, File(description="WebM, OGG, WAV o MP3 de hasta 2 min y 10 MB")],
    formatos: Annotated[list[FormatoReporte] | None, Form()] = None,
    usuario: UsuarioAutenticado = Depends(solo_gerencia),
    servicio: ServicioReportes = Depends(servicio_reportes),
) -> JSONResponse:
    limite = int(request.app.state.configuracion.reportes_tamanio_maximo_audio_mb * BLOQUE)
    sufijo = Path(audio.filename or "").suffix.lower()
    with tempfile.TemporaryDirectory() as carpeta:
        local = Path(carpeta) / f"audio{sufijo if sufijo in EXTENSIONES_AUDIO else '.webm'}"
        total = 0
        with local.open("wb") as salida:
            while bloque := await audio.read(BLOQUE):
                total += len(bloque)
                if total > limite:
                    raise ErrorAplicacion(
                        400,
                        "ARCHIVO_DEMASIADO_GRANDE",
                        "El archivo supera el tamaño máximo permitido.",
                    )
                salida.write(bloque)
        trabajo = await servicio.solicitar_voz(local, formatos, usuario)
    return respuesta_creado(trabajo)


@router_reportes.get(
    "/reportes/fuentes",
    summary="Fuentes de datos, campos y operadores para armar planes de reporte",
    responses=respuestas_error(400, 401, 403, 500),
)
async def fuentes(
    _: UsuarioAutenticado = Depends(gerencia_o_programados),
) -> list[FuenteCatalogo]:
    return [
        FuenteCatalogo(
            nombre=f.nombre,
            descripcion=f.descripcion,
            de_una_campania=f.de_una_campania,
            campos=[
                CampoCatalogo(
                    nombre=c.nombre,
                    etiqueta=c.etiqueta,
                    tipo=c.tipo.value,
                    valores=list(c.valores),
                    por_defecto=c.por_defecto,
                    operadores=sorted(o.value for o in OPERADORES_POR_TIPO[c.tipo]),
                )
                for c in f.campos
            ],
        )
        for f in FUENTES.values()
    ]


@router_reportes.get(
    "/reportes/{id_trabajo}/archivos/{formato}",
    summary="Descargar un archivo del reporte (solo su solicitante, durante 7 días)",
    responses={
        **respuestas_error(400, 401, 403, 404, 409, 500, 503),
        304: {"description": "Sin cambios"},
    },
    response_class=Response,
)
async def descargar(
    id_trabajo: str,
    formato: str,
    si_no_coincide: Annotated[str | None, Header(alias="If-None-Match")] = None,
    usuario: UsuarioAutenticado = Depends(usuario_actual),
    servicio: ServicioReportes = Depends(servicio_reportes),
) -> Response:
    archivo = await servicio.descargar(id_trabajo, formato, usuario)
    etag = f'"{archivo.sha256}"'
    encabezados = {
        "ETag": etag,
        "Cache-Control": "private, max-age=3600",
        "Content-Disposition": f'attachment; filename="{archivo.nombre}"; '
        f"filename*=UTF-8''{quote(archivo.nombre)}",
    }
    if si_no_coincide and etag in {v.strip().removeprefix("W/") for v in si_no_coincide.split(",")}:
        return Response(status_code=304, headers=encabezados)
    return Response(content=archivo.datos, media_type=archivo.tipo_contenido, headers=encabezados)
