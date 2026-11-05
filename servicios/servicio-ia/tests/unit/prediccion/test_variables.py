"""prediccion/variables.py (spec-prediccion.md 2.4)."""

import pytest

from app.prediccion.variables import (
    CategoriaCosto,
    Cultivo,
    Referencia,
    calcular_referencia,
    fuera_de_rango,
    motivos_anomalia,
    normalizar_cultivo,
    perfil_patrones,
    vector_rendimiento,
)

C = CategoriaCosto


def _costos(insumo: float, mano: float = 100, maquinaria: float = 300, otro: float = 100) -> dict:
    return {C.INSUMO: insumo, C.MANO_DE_OBRA: mano, C.MAQUINARIA: maquinaria, C.OTRO: otro}


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("Soya", Cultivo.SOYA),
        ("  SOJA ", Cultivo.SOYA),
        ("Maíz", Cultivo.MAIZ),
        ("maiz   amarillo", Cultivo.MAIZ),
        ("Maíz Duro", Cultivo.MAIZ),
        ("Sorgo granífero", Cultivo.SORGO),
        ("Trigo", None),
        ("Soya Munasqa", Cultivo.SOYA),
        ("Maíz amarillo duro", Cultivo.MAIZ),
        ("Soya E2E 2515f4b4", Cultivo.SOYA),
        ("Trigo soya", None),
        ("", None),
    ],
)
def test_normalizar_cultivo(nombre: str, esperado: Cultivo | None) -> None:
    assert normalizar_cultivo(nombre) is esperado


def test_vector_rendimiento_one_hot_y_costos_en_orden() -> None:
    assert vector_rendimiento(Cultivo.MAIZ, _costos(500)) == [0, 1, 0, 500, 100, 300, 100]


@pytest.fixture
def referencia() -> Referencia:
    filas = [
        (Cultivo.SOYA, _costos(insumo), rendimiento)
        for insumo, rendimiento in [(400, 2500), (500, 3000), (600, 3500)]
    ]
    filas += [(Cultivo.MAIZ, _costos(1000, 200, 600, 200), 9000)]
    return calcular_referencia(filas)


def test_referencia_por_cultivo(referencia: Referencia) -> None:
    soya = referencia.cultivos["SOYA"]
    assert soya.mediana_costo_total == 1000
    assert soya.mediana_rendimiento == 3000
    assert soya.minimos["INSUMO"] == 400
    assert soya.maximos["INSUMO"] == 600
    assert "SORGO" not in referencia.cultivos
    assert len(referencia.perfil_media) == len(referencia.perfil_desviacion) == 6


def test_referencia_se_serializa_y_vuelve(referencia: Referencia) -> None:
    assert Referencia.desde_dict(referencia.a_dict()) == referencia


def test_perfil_relativo_al_cultivo(referencia: Referencia) -> None:
    perfil = perfil_patrones(Cultivo.SOYA, _costos(500), 3000, referencia)

    assert perfil == [1.0, 1.0, 0.5, 0.1, 0.3, 0.1]


def test_fuera_de_rango(referencia: Referencia) -> None:
    assert fuera_de_rango(Cultivo.SOYA, _costos(500), referencia) == []
    assert fuera_de_rango(Cultivo.SOYA, _costos(1201), referencia) == ["INSUMO"]
    assert fuera_de_rango(Cultivo.SOYA, _costos(199, mano=1000), referencia) == [
        "INSUMO",
        "MANO_DE_OBRA",
    ]


def test_motivos_de_anomalia_en_espanol() -> None:
    referencia = Referencia(
        cultivos={},
        perfil_media=[1, 1, 0.5, 0.1, 0.3, 0.1],
        perfil_desviacion=[0.2, 0.2, 0.1, 0.05, 0.1, 0.05],
    )

    motivos = motivos_anomalia([2.4, 1.1, 0.8, 0.1, 0.3, 0.1], referencia)

    assert motivos == [
        "Costo total por hectárea 2,4 veces el típico del cultivo",
        "Participación de insumos en el costo de 80 % (típico: 50 %)",
    ]
