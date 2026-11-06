"""Interpretación de las probabilidades del modelo (spec-vision.md 2.6)."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.vision.etiquetas import INDETERMINADO

CUATRO_DECIMALES = Decimal("0.0001")
CANTIDAD_ALTERNATIVAS = 3


def a_confianza(probabilidad: float) -> Decimal:
    """Texto decimal de 0 a 1 con 4 decimales, mitad hacia arriba (formato de operaciones)."""
    return Decimal(str(float(probabilidad))).quantize(CUATRO_DECIMALES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Resultado:
    categoria: str
    confianza: Decimal
    alternativas: list[tuple[str, Decimal]]  # las 3 más probables, sin la elegida


def interpretar(
    probabilidades: Sequence[float], categorias: Sequence[str], umbral: float
) -> Resultado:
    """Categoría más probable, o `INDETERMINADO` si no llega al umbral, y sus alternativas."""
    orden = np.argsort(np.asarray(probabilidades))[::-1][:CANTIDAD_ALTERNATIVAS]
    top = [(categorias[i], a_confianza(probabilidades[i])) for i in orden]
    if float(probabilidades[orden[0]]) < umbral:
        return Resultado(INDETERMINADO, top[0][1], top)
    return Resultado(top[0][0], top[0][1], top[1:])


def predecir(modelo: Any, lote: NDArray[np.float32]) -> NDArray[np.float32]:
    """Probabilidades del modelo para un lote (N, 224, 224, 3); corre en un hilo."""
    return np.asarray(modelo(lote, training=False), dtype=np.float32)
