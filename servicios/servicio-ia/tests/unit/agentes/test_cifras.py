"""Verificación de cifras (spec-agentes.md, Historia 2; 2.6)."""

from decimal import Decimal

import pytest

from app.agentes.cifras import (
    SIN_CIFRAS_VERIFICABLES,
    Verificacion,
    lecturas,
    oraciones,
    verificar,
)

INVENTARIO = {
    "resumen": {"totalInsumos": 3, "totalStockBajo": 2},
    "items": [
        {
            "idInsumo": "71aa0c2e-5d4b-4c1e-9a77-3f0e1b2c4d5e",
            "nombre": "Glifosato",
            "stock": "20.000",
            "nivelMinimo": "20.000",
            "fechaUltimaAlerta": "2026-11-02T10:15:00Z",
        },
        {"idInsumo": "b2", "nombre": "Urea", "stock": "150.500", "nivelMinimo": "300.000"},
    ],
    "total": 2,
    "truncado": False,
}
CAMPANIA = {
    "costoTotal": "38250.00",
    "rendimientoPorHectarea": "3000.00",
    "costoPorHectarea": "1530.4567",
}


def test_todas_las_cifras_respaldadas_se_devuelve_completa() -> None:
    texto = "Hay 2 insumos con stock bajo. Glifosato tiene 20 litros, igual a su nivel mínimo."

    resultado = verificar(texto, [INVENTARIO])

    assert resultado == Verificacion(texto, 0)


def test_una_cifra_inventada_quita_solo_su_oracion() -> None:
    texto = (
        "Hay 2 insumos con stock bajo. En promedio les faltan 64,75 litros. Urea tiene 150,5 kg."
    )

    resultado = verificar(texto, [INVENTARIO])

    assert resultado.texto == "Hay 2 insumos con stock bajo. Urea tiene 150,5 kg."
    assert resultado.omitidas == 1


def test_si_se_quitan_todas_queda_el_texto_fijo() -> None:
    resultado = verificar("El costo promedio fue 12.345 Bs. Subió un 17 %.", [CAMPANIA])

    assert resultado.texto == SIN_CIFRAS_VERIFICABLES
    assert resultado.omitidas == 2


@pytest.mark.parametrize(
    "texto",
    [
        "El costo total fue 38.250,00 Bs.",
        "El costo total fue 38250 Bs.",
        "El costo total fue 38 250 Bs.",
        "El costo total fue 38,250.00 Bs.",
        "El rendimiento fue 3.000 kg/ha.",
        "El rendimiento fue 3000kg/ha.",
        "El costo por hectárea fue 1.530,46 Bs.",
        "El costo por hectárea fue 1530,5 Bs.",
        "El costo por hectárea fue 1.530 Bs.",
    ],
)
def test_otros_formatos_de_la_misma_cifra(texto: str) -> None:
    assert verificar(texto, [CAMPANIA]).omitidas == 0


@pytest.mark.parametrize(
    "texto", ["Quedan 20 litros.", "Quedan 20.000 litros.", "Quedan 20,000 l."]
)
def test_stock_con_punto_decimal_de_inventario(texto: str) -> None:
    assert verificar(texto, [INVENTARIO]).omitidas == 0


def test_fechas_anios_e_ids_de_los_datos_no_son_cifras_sin_respaldo() -> None:
    texto = "La última alerta fue el 02/11/2026 a las 10:15. En 2026 hubo alertas."

    assert verificar(texto, [INVENTARIO]).omitidas == 0


def test_la_cifra_de_la_pregunta_cuenta_como_respaldada() -> None:
    texto = "Ninguna campaña costó más de 30.000 Bs."

    assert (
        verificar(texto, [CAMPANIA], pregunta="¿Qué campañas costaron más de 30000?").omitidas == 0
    )
    assert verificar(texto, [CAMPANIA]).omitidas == 1


def test_contar_los_elementos_listados_esta_respaldado() -> None:
    datos = {"items": [{"nombre": "A"}, {"nombre": "B"}, {"nombre": "C"}], "truncado": False}

    assert verificar("Hay 3 parcelas.", [datos]).omitidas == 0
    assert verificar("Hay 4 parcelas.", [datos]).omitidas == 1


def test_numeros_dentro_de_palabras_no_son_cifras() -> None:
    assert verificar("El reporte COVID19 no aplica.", []).omitidas == 0


def test_conserva_las_lineas_de_una_lista() -> None:
    texto = "Insumos con stock bajo:\n- Glifosato: 20 litros.\n- Urea: 999 kg.\n- Urea: 150,5 kg."

    resultado = verificar(texto, [INVENTARIO])

    assert resultado.texto == "Insumos con stock bajo:\n- Glifosato: 20 litros.\n- Urea: 150,5 kg."
    assert resultado.omitidas == 1


def test_lecturas_ambiguas() -> None:
    assert lecturas("20.000") == {Decimal("20.000"), Decimal("20000")}
    assert lecturas("1,500") == {Decimal("1.5"), Decimal("1500")}
    assert lecturas("38.250,00") == {Decimal("38250.00")}
    assert lecturas("3000.00") == {Decimal("3000.00")}
    assert lecturas("1.234.567") == {Decimal("1234567")}
    assert lecturas("1.2.3") == set()


def test_division_en_oraciones_respeta_los_decimales() -> None:
    assert oraciones("Tiene 20.5 kg. Bien!  Otra") == [["Tiene 20.5 kg.", "Bien!", "Otra"]]
