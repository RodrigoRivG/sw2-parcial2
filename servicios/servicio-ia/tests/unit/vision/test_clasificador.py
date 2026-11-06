"""vision/clasificador.py y etiquetas (spec-vision.md, Historia 1, escenarios 1 y 2)."""

from decimal import Decimal

import numpy as np

from app.vision.clasificador import a_confianza, interpretar, predecir
from app.vision.etiquetas import CATEGORIAS, ETIQUETAS, INDETERMINADO, etiqueta

CATS = ["A", "B", "C", "D"]


def test_doce_etiquetas_en_orden_alfabetico_con_tipos_de_operaciones() -> None:
    assert len(ETIQUETAS) == 12
    assert list(CATEGORIAS) == sorted(CATEGORIAS)
    assert {e.tipo_incidencia_sugerido for e in ETIQUETAS} <= {"ENFERMEDAD", "OTRO", None}
    assert etiqueta("SOYA_ROYA").nombre == "Roya asiática de la soya"
    assert etiqueta(INDETERMINADO).cultivo is None


def test_elige_la_mas_probable_y_dos_alternativas() -> None:
    resultado = interpretar([0.05, 0.873149, 0.07, 0.006851], CATS, umbral=0.5)

    assert resultado.categoria == "B"
    assert resultado.confianza == Decimal("0.8731")
    assert resultado.alternativas == [("C", Decimal("0.0700")), ("A", Decimal("0.0500"))]


def test_bajo_el_umbral_es_indeterminado_con_tres_alternativas() -> None:
    resultado = interpretar([0.40, 0.35, 0.20, 0.05], CATS, umbral=0.5)

    assert resultado.categoria == INDETERMINADO
    assert resultado.confianza == Decimal("0.4000")
    assert [c for c, _ in resultado.alternativas] == ["A", "B", "C"]


def test_confianza_redondea_mitad_hacia_arriba() -> None:
    assert a_confianza(0.12345) == Decimal("0.1235")
    assert a_confianza(1.0) == Decimal("1.0000")


def test_predecir_llama_al_modelo_sin_entrenamiento() -> None:
    llamadas = []

    def modelo(lote: np.ndarray, training: bool) -> np.ndarray:
        llamadas.append(training)
        return np.full((len(lote), 4), 0.25)

    probabilidades = predecir(modelo, np.zeros((2, 224, 224, 3), dtype=np.float32))

    assert probabilidades.shape == (2, 4)
    assert llamadas == [False]
