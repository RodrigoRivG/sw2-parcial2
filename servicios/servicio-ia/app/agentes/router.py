"""`POST /consultas-agente` (spec-agentes.md 2.7)."""

from fastapi import Depends
from fastapi.responses import JSONResponse

from app.agentes.esquemas import SolicitudConsulta
from app.agentes.servicio import ServicioAgentes, servicio_agentes
from app.comun.errores import respuestas_error
from app.comun.seguridad import UsuarioAutenticado, requerir_roles, router_protegido
from app.trabajos.servicio import respuesta_creado

router_agentes = router_protegido(tags=["agentes"])
solo_gerencia = requerir_roles("gerencia")


@router_agentes.post(
    "/consultas-agente",
    status_code=202,
    summary="Preguntar en lenguaje natural sobre campañas o inventario (trabajo asíncrono)",
    responses=respuestas_error(400, 401, 403, 500, 503),
)
async def consultar(
    solicitud: SolicitudConsulta,
    usuario: UsuarioAutenticado = Depends(solo_gerencia),
    servicio: ServicioAgentes = Depends(servicio_agentes),
) -> JSONResponse:
    trabajo = await servicio.solicitar(solicitud.pregunta, usuario)
    return respuesta_creado(trabajo)
