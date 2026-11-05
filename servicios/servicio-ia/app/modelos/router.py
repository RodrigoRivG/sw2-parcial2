"""GET /modelos y publicación de versiones (spec-prediccion.md 2.8)."""

from typing import Annotated

from fastapi import Depends, Query

from app.comun.errores import respuestas_error
from app.comun.seguridad import UsuarioAutenticado, requerir_roles, router_protegido
from app.modelos.esquemas import RespuestaVersion, SolicitudPublicacion
from app.modelos.servicio import ServicioModelos, servicio_modelos

router_modelos = router_protegido(tags=["modelos"])


@router_modelos.get(
    "/modelos",
    summary="Listar las versiones de los modelos con su estado y métricas",
    responses=respuestas_error(400, 401, 403, 500, 503),
)
async def listar_versiones(
    nombre: Annotated[str | None, Query(max_length=50)] = None,
    _: UsuarioAutenticado = Depends(requerir_roles("administrador", "gerencia")),
    servicio: ServicioModelos = Depends(servicio_modelos),
) -> list[RespuestaVersion]:
    return [RespuestaVersion.desde(v) for v in await servicio.listar(nombre)]


@router_modelos.post(
    "/modelos/{nombre}/versiones/{version}/publicacion",
    summary="Publicar una versión candidata (pasa a vigente y retira la anterior)",
    responses=respuestas_error(400, 401, 403, 404, 409, 422, 500, 503),
)
async def publicar_version(
    nombre: str,
    version: int,
    cuerpo: SolicitudPublicacion | None = None,
    _: UsuarioAutenticado = Depends(requerir_roles("administrador")),
    servicio: ServicioModelos = Depends(servicio_modelos),
) -> RespuestaVersion:
    justificacion = cuerpo.justificacion if cuerpo else None
    return RespuestaVersion.desde(await servicio.publicar(nombre, version, justificacion))
