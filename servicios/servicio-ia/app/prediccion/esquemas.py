"""Solicitudes y respuestas de predicción y análisis (spec-prediccion.md 2.8)."""

import uuid
from datetime import date
from enum import StrEnum

from pydantic import Field, model_validator

from app.comun.esquemas import DecimalTexto, FechaHoraUtc, ModeloBase, ModeloEntrada
from app.modelos.esquemas import ReferenciaVersion

AVISO_PREDICCION = (
    "Estimación orientativa basada en datos de referencia. "
    "No sustituye una evaluación técnica agrícola."
)
AVISO_ANALISIS = (
    "Agrupaciones y anomalías orientativas. No sustituyen una evaluación técnica agrícola."
)


class OrigenCostos(StrEnum):
    REGISTRADOS = "REGISTRADOS"
    SIMULADOS = "SIMULADOS"


class CostosPorHectarea(ModeloEntrada):
    """Las cuatro categorías de CostoCampania, en BOB por hectárea."""

    INSUMO: DecimalTexto = Field(alias="INSUMO")
    MANO_DE_OBRA: DecimalTexto = Field(alias="MANO_DE_OBRA")
    MAQUINARIA: DecimalTexto = Field(alias="MAQUINARIA")
    OTRO: DecimalTexto = Field(alias="OTRO")

    @model_validator(mode="after")
    def _no_negativos(self) -> "CostosPorHectarea":
        if any(v < 0 for v in (self.INSUMO, self.MANO_DE_OBRA, self.MAQUINARIA, self.OTRO)):
            raise ValueError("Los costos por hectárea no pueden ser negativos.")
        return self


class SolicitudPrediccion(ModeloEntrada):
    id_campania: uuid.UUID
    costos_por_hectarea: CostosPorHectarea | None = None


class Intervalo(ModeloBase):
    minimo: DecimalTexto
    maximo: DecimalTexto


class Advertencia(ModeloBase):
    codigo: str
    mensaje: str
    campos: list[str]


class Prediccion(ModeloBase):
    id: str
    id_campania: str
    fecha: FechaHoraUtc
    cultivo: str
    estado_campania: str
    origen_costos: OrigenCostos
    costos_por_hectarea: dict[str, DecimalTexto]
    rendimiento_estimado: DecimalTexto
    intervalo: Intervalo
    produccion_estimada: DecimalTexto
    rendimiento_real: DecimalTexto | None
    unidad: str = "kg/ha"
    advertencias: list[Advertencia]
    version_modelo: ReferenciaVersion
    orientativo: bool = True
    aviso: str = AVISO_PREDICCION


class SolicitudAnalisis(ModeloEntrada):
    id_cultivo: uuid.UUID | None = None
    fecha_finalizacion_desde: date | None = None
    fecha_finalizacion_hasta: date | None = None

    @model_validator(mode="after")
    def _rango(self) -> "SolicitudAnalisis":
        desde, hasta = self.fecha_finalizacion_desde, self.fecha_finalizacion_hasta
        if desde and hasta and desde > hasta:
            raise ValueError("La fecha desde no puede ser posterior a la fecha hasta.")
        return self


class Grupo(ModeloBase):
    grupo: int
    descripcion: str
    cantidad: int
    ids_campania: list[str]


class Anomalia(ModeloBase):
    id_campania: str
    nombre_parcela: str | None
    cultivo: str
    puntaje: DecimalTexto
    motivos: list[str]


class Excluida(ModeloBase):
    id_campania: str
    motivo: str


class Analisis(ModeloBase):
    id: str
    fecha: FechaHoraUtc
    filtros: dict[str, str]
    cantidad_analizadas: int
    truncado: bool
    grupos: list[Grupo]
    anomalias: list[Anomalia]
    excluidas: list[Excluida]
    version_modelo: ReferenciaVersion
    orientativo: bool = True
    aviso: str = AVISO_ANALISIS


class ResumenAnalisis(ModeloBase):
    id: str
    fecha: FechaHoraUtc
    filtros: dict[str, str]
    cantidad_analizadas: int
    truncado: bool
    cantidad_grupos: int
    cantidad_anomalias: int
    version_modelo: ReferenciaVersion


class Pagina[T](ModeloBase):
    items: list[T]
    pagina: int
    tamanio: int
    total: int
