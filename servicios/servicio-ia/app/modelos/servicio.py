"""Listado y publicación de versiones (spec-prediccion.md, Historia 3)."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import Request

from app.comun.errores import ErrorAplicacion
from app.integracion.errores import ErrorInfraestructura
from app.integracion.repositorio_versiones import RepositorioVersionesFirestore
from app.modelos.cargador import CargadorModelos
from app.modelos.esquemas import EstadoVersion, MetricaPrincipal, VersionModelo
from app.modelos.reglas import puede_publicar

MENSAJE_METRICAS_INFERIORES = (
    "Las métricas de la versión son peores que las de la vigente. "
    "Indique una justificación para publicarla."
)


def _ahora() -> datetime:
    return datetime.now(UTC)


class ServicioModelos:
    def __init__(
        self,
        repositorio: RepositorioVersionesFirestore,
        cargador: CargadorModelos,
        reloj: Callable[[], datetime] = _ahora,
    ) -> None:
        self._repositorio = repositorio
        self._cargador = cargador
        self._reloj = reloj

    async def listar(self, nombre: str | None) -> list[VersionModelo]:
        try:
            documentos = await self._repositorio.listar(nombre)
        except ErrorInfraestructura:
            raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None
        return [VersionModelo.desde_documento(d) for d in documentos]

    async def publicar(self, nombre: str, version: int, justificacion: str | None) -> VersionModelo:
        ahora = self._reloj()

        def verificar(candidata: dict[str, Any], vigente: dict[str, Any] | None) -> dict[str, Any]:
            if candidata["estado"] != EstadoVersion.CANDIDATA.value:
                raise ErrorAplicacion(
                    409, "VERSION_NO_PUBLICABLE", "Solo se puede publicar una versión candidata."
                )
            metrica = MetricaPrincipal.model_validate(candidata["metricaPrincipal"])
            metrica_vigente = (
                MetricaPrincipal.model_validate(vigente["metricaPrincipal"]) if vigente else None
            )
            if not puede_publicar(metrica, metrica_vigente, justificacion):
                raise ErrorAplicacion(422, "METRICAS_INFERIORES", MENSAJE_METRICAS_INFERIORES)
            texto = justificacion.strip() if justificacion and justificacion.strip() else None
            return {"fechaPublicacion": ahora, "justificacion": texto}

        try:
            documento = await self._repositorio.publicar(nombre, version, verificar)
        except ErrorInfraestructura:
            raise ErrorAplicacion(503, "DEPENDENCIA_NO_DISPONIBLE") from None
        if documento is None:
            raise ErrorAplicacion(
                404, "VERSION_MODELO_NO_ENCONTRADA", "La versión del modelo no existe."
            )
        self._cargador.revisar_en_segundo_plano(nombre)  # esta instancia, sin esperar el ciclo
        return VersionModelo.desde_documento(documento)


def servicio_modelos(request: Request) -> ServicioModelos:
    servicio: ServicioModelos = request.app.state.servicio_modelos
    return servicio


def cargador_modelos(request: Request) -> CargadorModelos:
    cargador: CargadorModelos = request.app.state.cargador_modelos
    return cargador
