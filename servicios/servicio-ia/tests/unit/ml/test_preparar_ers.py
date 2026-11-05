"""Transformación del dataset ERS (spec-prediccion.md, Historia 4, y 2.3)."""

import csv
import json
from decimal import Decimal
from pathlib import Path

from app.ml.datos.preparar_ers import preparar, transformar

ITEMS = {
    "Seed": "10",
    "Fertilizer  ": "20",  # el ERS deja espacios al final de algunos ítems
    "Chemicals": "30",
    "Custom services  ": "1",
    "Fuel, lube, and electricity": "2",
    "Repairs": "3",
    "Capital recovery of machinery and equipment": "4",
    "Hired labor": "5",
    "Purchased irrigation water": "0",
    "Interest on operating capital": "1",
    "Taxes and insurance": "2",
    "General farm overhead": "3",
    "Opportunity cost of land": "999",  # se excluye
    "Opportunity cost of unpaid labor": "999",  # se excluye
}
IPC = {2024: Decimal("100"), 2025: Decimal("110")}
FACTOR_COSTO = Decimal("2.47105") * Decimal("6.96")


def _filas(
    region: str = "Heartland",
    anio: int = 2025,
    rendimiento: str = "50",
    items: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    filas = [
        {
            "Region": region,
            "Units": "dollars per planted acre",
            "Item": item,
            "Year": str(anio),
            "Value": valor,
        }
        for item, valor in (items or ITEMS).items()
    ]
    filas.append(
        {
            "Region": region,
            "Units": "bushels per planted acre",
            "Item": "Yield",
            "Year": str(anio),
            "Value": rendimiento,
        }
    )
    filas.append(
        {
            "Region": region,
            "Units": "percent of acres",
            "Item": "Irrigated",
            "Year": str(anio),
            "Value": "5",
        }
    )
    return filas


def test_agrupa_por_categoria_y_convierte_unidades() -> None:
    (fila,), resumen = transformar({"SOYA": _filas()}, IPC)

    assert resumen.anio_base == 2025
    assert fila["origen"] == "ERS"
    assert (fila["cultivo"], fila["region"], fila["anio"]) == ("SOYA", "Heartland", 2025)
    assert fila["costoInsumoHa"] == (60 * FACTOR_COSTO).quantize(Decimal("0.01"))
    assert fila["costoMaquinariaHa"] == (10 * FACTOR_COSTO).quantize(Decimal("0.01"))
    assert fila["costoManoDeObraHa"] == (5 * FACTOR_COSTO).quantize(Decimal("0.01"))
    assert fila["costoOtroHa"] == (6 * FACTOR_COSTO).quantize(Decimal("0.01"))
    assert fila["rendimientoHa"] == (50 * Decimal("27.2155") * Decimal("2.47105")).quantize(
        Decimal("0.01")
    )


def test_maiz_y_sorgo_usan_25_4012_kg_por_bushel_y_el_interes_del_sorgo() -> None:
    items_sorgo = {
        ("Interest on operating inputs" if k == "Interest on operating capital" else k): v
        for k, v in ITEMS.items()
    }
    filas, _ = transformar({"MAIZ": _filas(), "SORGO": _filas(items=items_sorgo)}, IPC)

    esperado = (50 * Decimal("25.4012") * Decimal("2.47105")).quantize(Decimal("0.01"))
    assert [f["rendimientoHa"] for f in filas] == [esperado, esperado]
    assert filas[1]["costoOtroHa"] == (6 * FACTOR_COSTO).quantize(Decimal("0.01"))


def test_deflacta_a_dolares_del_ultimo_anio() -> None:
    filas, _ = transformar({"SOYA": _filas(anio=2024) + _filas(anio=2025)}, IPC)

    del_2024, del_2025 = filas
    assert del_2024["costoInsumoHa"] == (60 * Decimal("1.1") * FACTOR_COSTO).quantize(
        Decimal("0.01")
    )
    assert del_2025["costoInsumoHa"] == (60 * FACTOR_COSTO).quantize(Decimal("0.01"))


def test_excluye_el_total_de_eeuu_y_descarta_filas_incompletas() -> None:
    incompletos = {k: v for k, v in ITEMS.items() if k != "Repairs"}
    filas, resumen = transformar(
        {
            "SOYA": _filas(region="U.S. total")
            + _filas(region="Heartland")
            + _filas(region="Prairie Gateway", items=incompletos)
            + _filas(region="Eastern Uplands", rendimiento="")
            + _filas(region="Fruitful Rim", anio=1990),  # sin IPC
        },
        IPC,
    )

    assert [f["region"] for f in filas] == ["Heartland"]
    assert resumen.filas_por_cultivo["SOYA"] == 1
    assert resumen.descartadas_por_cultivo["SOYA"] == 3


def test_preparar_escribe_csv_y_fuentes(tmp_path: Path) -> None:
    origen = tmp_path / "ers"
    destino = tmp_path / "referencia"
    origen.mkdir()
    destino.mkdir()
    (destino / "ipc_eeuu.csv").write_text("anio,ipc\n2024,100\n2025,110\n", encoding="utf-8")
    columnas = [
        "Commodity",
        "Category",
        "Item",
        "Units",
        "Size",
        "Region",
        "Country",
        "Year",
        "Value",
        "Survey base year",
    ]
    for archivo in ("corn.csv", "soybeans.csv", "sorghum.csv"):
        with (origen / archivo).open("w", encoding="utf-8-sig", newline="") as salida:
            escritor = csv.DictWriter(salida, fieldnames=columnas, restval="")
            escritor.writeheader()
            escritor.writerows(_filas())

    resumen = preparar(origen, destino)

    filas = list(csv.DictReader((destino / "campanias_referencia.csv").open(encoding="utf-8")))
    assert [f["cultivo"] for f in filas] == ["MAIZ", "SORGO", "SOYA"]
    assert filas[0]["costoInsumoHa"] == format((60 * FACTOR_COSTO).quantize(Decimal("0.01")), "f")
    fuentes = json.loads((destino / "fuentes.json").read_text(encoding="utf-8"))
    assert fuentes["ipc"]["anioBase"] == 2025
    assert set(fuentes["archivos"]) == {"MAIZ", "SOYA", "SORGO"}
    assert len(fuentes["archivos"]["MAIZ"]["sha256"]) == 64
    assert resumen.filas_por_cultivo == {"MAIZ": 1, "SOYA": 1, "SORGO": 1}
