"""Regla de publicación (spec-prediccion.md, Historia 3, escenario 5)."""

import pytest

from app.modelos.esquemas import MetricaPrincipal, Sentido
from app.modelos.reglas import puede_publicar


def _mae(valor: float) -> MetricaPrincipal:
    return MetricaPrincipal(nombre="mae", valor=valor, sentido=Sentido.MENOR_ES_MEJOR)


def _silueta(valor: float) -> MetricaPrincipal:
    return MetricaPrincipal(nombre="silueta", valor=valor, sentido=Sentido.MAYOR_ES_MEJOR)


JUSTIFICACION = "Se agregan campañas reales del sistema al entrenamiento."


def test_primera_version_se_publica_sin_comparar() -> None:
    assert puede_publicar(_mae(900), None, None)


@pytest.mark.parametrize(
    ("candidata", "vigente", "esperado"),
    [
        (_mae(600), _mae(640), True),
        (_mae(640), _mae(640), True),
        (_mae(700), _mae(640), False),
        (_silueta(0.30), _silueta(0.28), True),
        (_silueta(0.20), _silueta(0.28), False),
    ],
    ids=["mae-mejor", "mae-igual", "mae-peor", "silueta-mejor", "silueta-peor"],
)
def test_sin_justificacion_solo_si_no_es_peor(
    candidata: MetricaPrincipal, vigente: MetricaPrincipal, esperado: bool
) -> None:
    assert puede_publicar(candidata, vigente, None) is esperado


def test_peor_con_justificacion_se_publica() -> None:
    assert puede_publicar(_mae(700), _mae(640), JUSTIFICACION)


@pytest.mark.parametrize("justificacion", ["", "   ", "muy corta"])
def test_justificacion_demasiado_corta_no_alcanza(justificacion: str) -> None:
    assert not puede_publicar(_mae(700), _mae(640), justificacion)
