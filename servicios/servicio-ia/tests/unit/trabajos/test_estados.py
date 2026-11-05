from datetime import UTC, datetime, timedelta

import pytest

from app.trabajos.estados import (
    EstadoTrabajo,
    calcular_fecha_expiracion,
    calcular_fecha_limite,
    es_terminal,
    esta_vencido,
    puede_pasar,
)

E = EstadoTrabajo
AHORA = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("desde", "hacia"),
    [
        (E.EN_COLA, E.PROCESANDO),
        (E.EN_COLA, E.FALLIDO),
        (E.PROCESANDO, E.COMPLETADO),
        (E.PROCESANDO, E.FALLIDO),
    ],
)
def test_transiciones_permitidas(desde: EstadoTrabajo, hacia: EstadoTrabajo) -> None:
    assert puede_pasar(desde, hacia)


@pytest.mark.parametrize(
    ("desde", "hacia"),
    [
        (E.EN_COLA, E.COMPLETADO),
        (E.PROCESANDO, E.EN_COLA),
        (E.COMPLETADO, E.FALLIDO),
        (E.FALLIDO, E.PROCESANDO),
        (E.COMPLETADO, E.COMPLETADO),
    ],
)
def test_transiciones_prohibidas(desde: EstadoTrabajo, hacia: EstadoTrabajo) -> None:
    assert not puede_pasar(desde, hacia)


def test_solo_completado_y_fallido_son_terminales() -> None:
    assert [e for e in E if es_terminal(e)] == [E.COMPLETADO, E.FALLIDO]


def test_fecha_limite_suma_30_segundos_de_margen() -> None:
    assert calcular_fecha_limite(AHORA, timedelta(minutes=2)) == AHORA + timedelta(seconds=150)


def test_fecha_expiracion() -> None:
    assert calcular_fecha_expiracion(AHORA, 30) == AHORA + timedelta(days=30)


def test_procesando_vencido_solo_despues_de_su_limite() -> None:
    creado = AHORA - timedelta(hours=1)
    assert esta_vencido(E.PROCESANDO, creado, AHORA - timedelta(seconds=1), AHORA)
    assert not esta_vencido(E.PROCESANDO, creado, AHORA + timedelta(seconds=1), AHORA)
    assert not esta_vencido(E.PROCESANDO, creado, None, AHORA)


def test_en_cola_vencido_despues_de_diez_minutos() -> None:
    assert esta_vencido(E.EN_COLA, AHORA - timedelta(minutes=10, seconds=1), None, AHORA)
    assert not esta_vencido(E.EN_COLA, AHORA - timedelta(minutes=9), None, AHORA)


@pytest.mark.parametrize("estado", [E.COMPLETADO, E.FALLIDO])
def test_terminales_nunca_vencen(estado: EstadoTrabajo) -> None:
    assert not esta_vencido(estado, AHORA - timedelta(days=1), AHORA - timedelta(days=1), AHORA)
