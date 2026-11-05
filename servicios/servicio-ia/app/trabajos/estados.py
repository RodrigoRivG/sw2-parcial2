"""Estados de un trabajo y sus reglas: funciones puras (spec-trabajos.md 2.4)."""

from datetime import datetime, timedelta
from enum import StrEnum


class EstadoTrabajo(StrEnum):
    EN_COLA = "EN_COLA"
    PROCESANDO = "PROCESANDO"
    COMPLETADO = "COMPLETADO"
    FALLIDO = "FALLIDO"


TRANSICIONES: dict[EstadoTrabajo, frozenset[EstadoTrabajo]] = {
    EstadoTrabajo.EN_COLA: frozenset({EstadoTrabajo.PROCESANDO, EstadoTrabajo.FALLIDO}),
    EstadoTrabajo.PROCESANDO: frozenset({EstadoTrabajo.COMPLETADO, EstadoTrabajo.FALLIDO}),
    EstadoTrabajo.COMPLETADO: frozenset(),
    EstadoTrabajo.FALLIDO: frozenset(),
}

MARGEN_LIMITE = timedelta(seconds=30)
ESPERA_MAXIMA_EN_COLA = timedelta(minutes=10)


def puede_pasar(desde: EstadoTrabajo, hacia: EstadoTrabajo) -> bool:
    return hacia in TRANSICIONES[desde]


def es_terminal(estado: EstadoTrabajo) -> bool:
    return not TRANSICIONES[estado]


def calcular_fecha_limite(fecha_inicio: datetime, tiempo_limite: timedelta) -> datetime:
    return fecha_inicio + tiempo_limite + MARGEN_LIMITE


def calcular_fecha_expiracion(fecha_fin: datetime, dias_retencion: int) -> datetime:
    return fecha_fin + timedelta(days=dias_retencion)


def esta_vencido(
    estado: EstadoTrabajo,
    fecha_creacion: datetime,
    fecha_limite: datetime | None,
    ahora: datetime,
) -> bool:
    """`PROCESANDO` después de su fecha límite, o `EN_COLA` más de 10 minutos."""
    if estado is EstadoTrabajo.PROCESANDO:
        return fecha_limite is not None and fecha_limite < ahora
    if estado is EstadoTrabajo.EN_COLA:
        return fecha_creacion < ahora - ESPERA_MAXIMA_EN_COLA
    return False
