"""Etiquetas del clasificador de imágenes (spec-vision.md 1.1).

El orden de `ETIQUETAS` (alfabético por categoría) es el orden de salida del modelo: el índice
de cada etiqueta es su posición en el vector de probabilidades, en el servidor y en los
dispositivos.
"""

from dataclasses import dataclass

INDETERMINADO = "INDETERMINADO"
UMBRAL_POR_DEFECTO = 0.50


@dataclass(frozen=True)
class Etiqueta:
    categoria: str
    nombre: str
    cultivo: str | None
    tipo_incidencia_sugerido: str | None  # valores de TipoIncidencia de servicio-operaciones


_TABLA = [
    Etiqueta("MAIZ_MANCHA_GRIS", "Mancha gris de la hoja", "MAIZ", "ENFERMEDAD"),
    Etiqueta("MAIZ_ROYA_COMUN", "Roya común del maíz", "MAIZ", "ENFERMEDAD"),
    Etiqueta("MAIZ_SANO", "Maíz sano", "MAIZ", None),
    Etiqueta("MAIZ_TIZON_NORTENO", "Tizón foliar del norte", "MAIZ", "ENFERMEDAD"),
    Etiqueta("SOYA_DEFICIENCIA_POTASIO", "Deficiencia de potasio", "SOYA", "OTRO"),
    Etiqueta("SOYA_MANCHA_DIANA", "Mancha diana", "SOYA", "ENFERMEDAD"),
    Etiqueta("SOYA_MANCHA_OJO_RANA", "Mancha ojo de rana", "SOYA", "ENFERMEDAD"),
    Etiqueta("SOYA_MILDIU", "Mildiu", "SOYA", "ENFERMEDAD"),
    Etiqueta("SOYA_ROYA", "Roya asiática de la soya", "SOYA", "ENFERMEDAD"),
    Etiqueta("SOYA_SANA", "Soya sana", "SOYA", None),
    Etiqueta("SOYA_TIZON_BACTERIANO", "Tizón bacteriano", "SOYA", "ENFERMEDAD"),
    Etiqueta("SOYA_TIZON_CERCOSPORA", "Tizón por Cercospora", "SOYA", "ENFERMEDAD"),
]
ETIQUETAS: tuple[Etiqueta, ...] = tuple(sorted(_TABLA, key=lambda e: e.categoria))
CATEGORIAS: tuple[str, ...] = tuple(e.categoria for e in ETIQUETAS)
ETIQUETA_INDETERMINADA = Etiqueta(
    INDETERMINADO, "No se pudo identificar con suficiente confianza", None, None
)
_POR_CATEGORIA = {e.categoria: e for e in (*ETIQUETAS, ETIQUETA_INDETERMINADA)}


def etiqueta(categoria: str) -> Etiqueta:
    return _POR_CATEGORIA[categoria]
