"""Variables de los modelos de rendimiento y patrones (spec-prediccion.md 2.4).

Funciones puras que usan el entrenamiento (`app/ml`) y la inferencia (`prediccion/servicio.py`),
para que ambos calculen exactamente lo mismo.
"""

import statistics
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class Cultivo(StrEnum):
    SOYA = "SOYA"
    MAIZ = "MAIZ"
    SORGO = "SORGO"


class CategoriaCosto(StrEnum):
    """Las categorías de CostoCampania de servicio-gestion, en orden fijo."""

    INSUMO = "INSUMO"
    MANO_DE_OBRA = "MANO_DE_OBRA"
    MAQUINARIA = "MAQUINARIA"
    OTRO = "OTRO"


CULTIVOS = list(Cultivo)
CATEGORIAS = list(CategoriaCosto)
CostosHa = Mapping[CategoriaCosto, float]

_SINONIMOS = {
    "soya": Cultivo.SOYA,
    "soja": Cultivo.SOYA,
    "maiz": Cultivo.MAIZ,
    "maiz amarillo": Cultivo.MAIZ,
    "maiz duro": Cultivo.MAIZ,
    "sorgo": Cultivo.SORGO,
    "sorgo granifero": Cultivo.SORGO,
}

NOMBRES_PERFIL = [
    "costo total por hectárea",
    "rendimiento por hectárea",
    "participación de insumos en el costo",
    "participación de mano de obra en el costo",
    "participación de maquinaria en el costo",
    "participación de otros costos en el costo",
]
UMBRAL_Z = 2.0


@dataclass(frozen=True)
class ReferenciaCultivo:
    mediana_costo_total: float
    mediana_rendimiento: float
    minimos: dict[str, float]
    maximos: dict[str, float]


@dataclass(frozen=True)
class Referencia:
    """Estadísticas del conjunto de entrenamiento; se guardan en los metadatos de la versión."""

    cultivos: dict[str, ReferenciaCultivo]
    perfil_media: list[float]
    perfil_desviacion: list[float]

    def a_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def desde_dict(cls, datos: Mapping[str, Any]) -> "Referencia":
        return cls(
            cultivos={c: ReferenciaCultivo(**v) for c, v in datos["cultivos"].items()},
            perfil_media=list(datos["perfil_media"]),
            perfil_desviacion=list(datos["perfil_desviacion"]),
        )


def _sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def normalizar_cultivo(nombre: str) -> Cultivo | None:
    """Nombre del cultivo de servicio-gestion → cultivo del modelo (sin tildes ni mayúsculas).

    Si el nombre completo no es un sinónimo, se usa la primera palabra: "Soya Munasqa" o
    "Maíz amarillo duro" son soya y maíz (una variedad no cambia el cultivo).
    """
    palabras = _sin_tildes(nombre).lower().split()
    if not palabras:
        return None
    return _SINONIMOS.get(" ".join(palabras)) or _SINONIMOS.get(palabras[0])


def costo_total(costos: CostosHa) -> float:
    return sum(costos[c] for c in CATEGORIAS)


def vector_rendimiento(cultivo: Cultivo, costos: CostosHa) -> list[float]:
    """One-hot del cultivo + los cuatro costos por hectárea."""
    return [1.0 if cultivo is c else 0.0 for c in CULTIVOS] + [float(costos[c]) for c in CATEGORIAS]


def perfil_patrones(
    cultivo: Cultivo, costos: CostosHa, rendimiento: float, referencia: Referencia
) -> list[float]:
    """Perfil comparable entre cultivos: relativo a la mediana del cultivo y participaciones."""
    total = costo_total(costos)
    ref = referencia.cultivos[cultivo.value]
    participaciones = [costos[c] / total if total > 0 else 0.0 for c in CATEGORIAS]
    return [
        total / ref.mediana_costo_total,
        rendimiento / ref.mediana_rendimiento,
        *participaciones,
    ]


def fuera_de_rango(cultivo: Cultivo, costos: CostosHa, referencia: Referencia) -> list[str]:
    """Categorías con un costo menor que la mitad del mínimo o mayor que el doble del máximo."""
    ref = referencia.cultivos[cultivo.value]
    return [
        c.value
        for c in CATEGORIAS
        if costos[c] < ref.minimos[c.value] / 2 or costos[c] > ref.maximos[c.value] * 2
    ]


def motivos_anomalia(perfil: list[float], referencia: Referencia) -> list[str]:
    """Variables del perfil con |z| > 2 respecto de la referencia, con plantillas fijas."""
    motivos: list[str] = []
    for indice, valor in enumerate(perfil):
        desviacion = referencia.perfil_desviacion[indice] or 1.0
        z = (valor - referencia.perfil_media[indice]) / desviacion
        if abs(z) <= UMBRAL_Z:
            continue
        nombre = NOMBRES_PERFIL[indice]
        if indice < 2:
            motivos.append(f"{nombre.capitalize()} {_numero(valor, 1)} veces el típico del cultivo")
        else:
            tipico = referencia.perfil_media[indice]
            motivos.append(
                f"{nombre.capitalize()} de {_numero(valor * 100, 0)} % "
                f"(típico: {_numero(tipico * 100, 0)} %)"
            )
    return motivos


def _numero(valor: float, decimales: int) -> str:
    """Formato español: coma decimal."""
    return f"{valor:.{decimales}f}".replace(".", ",")


def calcular_referencia(filas: Iterable[tuple[Cultivo, CostosHa, float]]) -> Referencia:
    """Estadísticas por cultivo y del perfil, a partir de las filas de entrenamiento."""
    datos = list(filas)
    cultivos: dict[str, ReferenciaCultivo] = {}
    for cultivo in CULTIVOS:
        propias = [(c, r) for cu, c, r in datos if cu is cultivo]
        if not propias:
            continue
        cultivos[cultivo.value] = ReferenciaCultivo(
            mediana_costo_total=statistics.median(costo_total(c) for c, _ in propias),
            mediana_rendimiento=statistics.median(r for _, r in propias),
            minimos={cat.value: min(c[cat] for c, _ in propias) for cat in CATEGORIAS},
            maximos={cat.value: max(c[cat] for c, _ in propias) for cat in CATEGORIAS},
        )
    parcial = Referencia(cultivos, [0.0] * len(NOMBRES_PERFIL), [1.0] * len(NOMBRES_PERFIL))
    perfiles = [perfil_patrones(cu, c, r, parcial) for cu, c, r in datos if cu.value in cultivos]
    columnas = list(zip(*perfiles, strict=True))
    return Referencia(
        cultivos=cultivos,
        perfil_media=[statistics.fmean(col) for col in columnas],
        perfil_desviacion=[statistics.pstdev(col) for col in columnas],
    )
