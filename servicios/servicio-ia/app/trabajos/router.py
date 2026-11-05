"""GET /api/ia/v1/trabajos/{id} (spec-trabajos.md 2.11)."""

from fastapi import Depends, Response

from app.comun.errores import respuestas_error
from app.comun.seguridad import UsuarioAutenticado, router_protegido, usuario_actual
from app.trabajos.esquemas import RespuestaTrabajo
from app.trabajos.estados import es_terminal
from app.trabajos.servicio import ServicioTrabajos, servicio_trabajos

router_trabajos = router_protegido(tags=["trabajos"])


@router_trabajos.get(
    "/trabajos/{id_trabajo}",
    summary="Consultar el estado y el resultado de un trabajo propio",
    responses=respuestas_error(400, 401, 403, 404, 500, 503),
)
async def obtener_trabajo(
    id_trabajo: str,
    response: Response,
    usuario: UsuarioAutenticado = Depends(usuario_actual),
    servicio: ServicioTrabajos = Depends(servicio_trabajos),
) -> RespuestaTrabajo:
    trabajo = await servicio.obtener_para(id_trabajo, usuario)
    if not es_terminal(trabajo.estado):
        response.headers["Retry-After"] = "2"
    return RespuestaTrabajo.desde(trabajo)
