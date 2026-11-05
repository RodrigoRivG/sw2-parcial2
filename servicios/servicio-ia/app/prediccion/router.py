"""Endpoints de predicción y análisis (spec-prediccion.md 2.8)."""

import uuid
from typing import Annotated

from fastapi import Depends, Query

from app.comun.errores import respuestas_error
from app.comun.seguridad import UsuarioAutenticado, requerir_roles, router_protegido
from app.prediccion.esquemas import (
    Analisis,
    Pagina,
    Prediccion,
    ResumenAnalisis,
    SolicitudAnalisis,
    SolicitudPrediccion,
)
from app.prediccion.servicio import ServicioPrediccion, servicio_prediccion

router_prediccion = router_protegido(tags=["prediccion"])

PaginaQuery = Annotated[int, Query(ge=0)]
TamanioQuery = Annotated[int, Query(ge=1, le=100)]
solo_gerencia = requerir_roles("gerencia")
lectura_resultados = requerir_roles("gerencia", "lectura_ia")


@router_prediccion.post(
    "/predicciones",
    status_code=201,
    summary="Estimar el rendimiento de una campaña (orientativo)",
    responses=respuestas_error(400, 401, 403, 404, 422, 500, 503),
)
async def estimar_rendimiento(
    solicitud: SolicitudPrediccion,
    usuario: UsuarioAutenticado = Depends(solo_gerencia),
    servicio: ServicioPrediccion = Depends(servicio_prediccion),
) -> Prediccion:
    return await servicio.estimar(
        str(solicitud.id_campania), solicitud.costos_por_hectarea, usuario
    )


@router_prediccion.get(
    "/predicciones",
    summary="Listar predicciones, de la más reciente a la más antigua",
    responses=respuestas_error(400, 401, 403, 500, 503),
)
async def listar_predicciones(
    id_campania: Annotated[uuid.UUID | None, Query(alias="idCampania")] = None,
    pagina: PaginaQuery = 0,
    tamanio: TamanioQuery = 20,
    _: UsuarioAutenticado = Depends(lectura_resultados),
    servicio: ServicioPrediccion = Depends(servicio_prediccion),
) -> Pagina[Prediccion]:
    return await servicio.listar_predicciones(
        str(id_campania) if id_campania else None, pagina, tamanio
    )


@router_prediccion.post(
    "/analisis",
    status_code=201,
    summary="Agrupar campañas finalizadas y detectar anomalías (orientativo)",
    responses=respuestas_error(400, 401, 403, 422, 500, 503),
)
async def analizar_patrones(
    solicitud: SolicitudAnalisis | None = None,
    usuario: UsuarioAutenticado = Depends(solo_gerencia),
    servicio: ServicioPrediccion = Depends(servicio_prediccion),
) -> Analisis:
    return await servicio.analizar(solicitud or SolicitudAnalisis(), usuario)


@router_prediccion.get(
    "/analisis",
    summary="Listar análisis, del más reciente al más antiguo",
    responses=respuestas_error(400, 401, 403, 500, 503),
)
async def listar_analisis(
    pagina: PaginaQuery = 0,
    tamanio: TamanioQuery = 20,
    _: UsuarioAutenticado = Depends(lectura_resultados),
    servicio: ServicioPrediccion = Depends(servicio_prediccion),
) -> Pagina[ResumenAnalisis]:
    return await servicio.listar_analisis(pagina, tamanio)


@router_prediccion.get(
    "/analisis/{id_analisis}",
    summary="Consultar un análisis",
    responses=respuestas_error(400, 401, 403, 404, 500, 503),
)
async def obtener_analisis(
    id_analisis: str,
    _: UsuarioAutenticado = Depends(lectura_resultados),
    servicio: ServicioPrediccion = Depends(servicio_prediccion),
) -> Analisis:
    return await servicio.obtener_analisis(id_analisis)
