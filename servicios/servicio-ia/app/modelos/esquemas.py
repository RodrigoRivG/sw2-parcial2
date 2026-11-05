"""Versión de un modelo (spec-prediccion.md 1.3, RQ-PRE-01)."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from app.comun.esquemas import FechaHoraUtc, ModeloBase, ModeloEntrada


class EstadoVersion(StrEnum):
    CANDIDATA = "CANDIDATA"
    VIGENTE = "VIGENTE"
    RETIRADA = "RETIRADA"


class Sentido(StrEnum):
    MENOR_ES_MEJOR = "MENOR_ES_MEJOR"
    MAYOR_ES_MEJOR = "MAYOR_ES_MEJOR"


class MetricaPrincipal(ModeloBase):
    nombre: str
    valor: float
    sentido: Sentido


class DatasetVersion(ModeloBase):
    ruta: str
    sha256: str
    filas_por_origen: dict[str, int]


class VersionModelo(ModeloBase):
    nombre: str
    version: int
    estado: EstadoVersion
    fecha_entrenamiento: datetime
    fecha_publicacion: datetime | None = None
    dataset: DatasetVersion
    variables: list[str]
    hiperparametros: dict[str, Any]
    semilla: int
    metricas: dict[str, Any]
    metrica_principal: MetricaPrincipal
    ruta_artefactos: str
    referencia: dict[str, Any] | None = None
    adicionales: dict[str, Any] = {}
    justificacion: str | None = None

    def a_documento(self) -> dict[str, Any]:
        documento = self.model_dump(by_alias=True, mode="python")
        documento["estado"] = self.estado.value
        documento["metricaPrincipal"]["sentido"] = self.metrica_principal.sentido.value
        return documento

    @classmethod
    def desde_documento(cls, documento: dict[str, Any]) -> "VersionModelo":
        return cls.model_validate(documento)


class RespuestaVersion(ModeloBase):
    nombre: str
    version: int
    estado: EstadoVersion
    fecha_entrenamiento: FechaHoraUtc
    fecha_publicacion: FechaHoraUtc | None
    filas_por_origen: dict[str, int]
    variables: list[str]
    hiperparametros: dict[str, Any]
    metricas: dict[str, Any]
    metrica_principal: MetricaPrincipal
    justificacion: str | None

    @classmethod
    def desde(cls, version: VersionModelo) -> "RespuestaVersion":
        return cls(
            nombre=version.nombre,
            version=version.version,
            estado=version.estado,
            fecha_entrenamiento=version.fecha_entrenamiento,
            fecha_publicacion=version.fecha_publicacion,
            filas_por_origen=version.dataset.filas_por_origen,
            variables=version.variables,
            hiperparametros=version.hiperparametros,
            metricas=version.metricas,
            metrica_principal=version.metrica_principal,
            justificacion=version.justificacion,
        )


class SolicitudPublicacion(ModeloEntrada):
    justificacion: str | None = None


class ReferenciaVersion(ModeloBase):
    """Versión del modelo que produjo un resultado (constitución §5)."""

    nombre: str
    version: int
