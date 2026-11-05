"""Conjunto de referencia desde el dataset público USDA ERS (spec-prediccion.md 2.3).

Uso (dentro del contenedor, desde la raíz del servicio):

    python -m app.ml.datos.preparar_ers            # descarga los CSV del ERS
    python -m app.ml.datos.preparar_ers --origen <carpeta con corn.csv, soybeans.csv, sorghum.csv>

Escribe `datos/referencia/campanias_referencia.csv` y `datos/referencia/fuentes.json`.
"""

import argparse
import csv
import hashlib
import io
import json
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import httpx

RAIZ_SERVICIO = Path(__file__).resolve().parents[3]
CARPETA_REFERENCIA = RAIZ_SERVICIO / "datos" / "referencia"

FUENTES_ERS: dict[str, tuple[str, str]] = {
    # cultivo del sistema: (archivo, URL de "Recent Cost and Returns")
    "MAIZ": ("corn.csv", "https://www.ers.usda.gov/media/4962/corn.csv"),
    "SOYA": ("soybeans.csv", "https://www.ers.usda.gov/media/4976/soybeans.csv"),
    "SORGO": ("sorghum.csv", "https://www.ers.usda.gov/media/4972/sorghum.csv"),
}

# Ítems del ERS (sin espacios al final) por categoría de CostoCampania de servicio-gestion
CATEGORIAS: dict[str, tuple[str, ...]] = {
    "INSUMO": ("Seed", "Fertilizer", "Chemicals"),
    "MAQUINARIA": (
        "Custom services",
        "Fuel, lube, and electricity",
        "Repairs",
        "Capital recovery of machinery and equipment",
    ),
    "MANO_DE_OBRA": ("Hired labor",),
    "OTRO": (
        "Purchased irrigation water",
        "Interest on operating capital|Interest on operating inputs",  # nombre en sorgo
        "Taxes and insurance",
        "General farm overhead",
    ),
}
# Se excluyen los costos implícitos que un productor no registra como gasto:
# "Opportunity cost of land" y "Opportunity cost of unpaid labor".

COLUMNAS_COSTO = {
    "INSUMO": "costoInsumoHa",
    "MANO_DE_OBRA": "costoManoDeObraHa",
    "MAQUINARIA": "costoMaquinariaHa",
    "OTRO": "costoOtroHa",
}
COLUMNAS = ["origen", "cultivo", "region", "anio", *COLUMNAS_COSTO.values(), "rendimientoHa"]

ACRES_POR_HECTAREA = Decimal("2.47105")
BOB_POR_USD = Decimal("6.96")
KG_POR_BUSHEL = {
    "SOYA": Decimal("27.2155"),
    "MAIZ": Decimal("25.4012"),
    "SORGO": Decimal("25.4012"),
}
UNIDAD_COSTO = "dollars per planted acre"
UNIDAD_RENDIMIENTO = "bushels per planted acre"
REGION_AGREGADA = "U.S. total"
DOS_DECIMALES = Decimal("0.01")


@dataclass
class Resumen:
    filas_por_cultivo: Counter[str] = field(default_factory=Counter)
    descartadas_por_cultivo: Counter[str] = field(default_factory=Counter)
    anio_base: int = 0


def _a_decimal(valor: str) -> Decimal | None:
    valor = valor.strip()
    if not valor:
        return None
    try:
        return Decimal(valor)
    except ArithmeticError:
        return None


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


def transformar(
    filas_por_cultivo: Mapping[str, Iterable[Mapping[str, str]]],
    ipc: Mapping[int, Decimal],
) -> tuple[list[dict[str, Any]], Resumen]:
    """Convierte las filas largas del ERS en una fila por cultivo, región y año (función pura)."""
    resumen = Resumen()
    salida: list[dict[str, Any]] = []
    anios: set[int] = set()
    agrupado: dict[tuple[str, str, int], dict[str, Decimal | None]] = defaultdict(dict)

    for cultivo, filas in filas_por_cultivo.items():
        for fila in filas:
            region = fila["Region"].strip()
            unidad = fila["Units"].strip()
            if region == REGION_AGREGADA or unidad not in (UNIDAD_COSTO, UNIDAD_RENDIMIENTO):
                continue
            item = fila["Item"].strip()
            anio = int(fila["Year"])
            anios.add(anio)
            agrupado[(cultivo, region, anio)][item] = _a_decimal(fila["Value"])

    resumen.anio_base = max(anios & set(ipc)) if anios & set(ipc) else 0
    for (cultivo, region, anio), valores in sorted(agrupado.items()):
        fila_salida = _fila(cultivo, region, anio, valores, ipc, resumen.anio_base)
        if fila_salida is None:
            resumen.descartadas_por_cultivo[cultivo] += 1
            continue
        resumen.filas_por_cultivo[cultivo] += 1
        salida.append(fila_salida)
    return salida, resumen


def _fila(
    cultivo: str,
    region: str,
    anio: int,
    valores: Mapping[str, Decimal | None],
    ipc: Mapping[int, Decimal],
    anio_base: int,
) -> dict[str, Any] | None:
    if anio not in ipc:
        return None
    rendimiento = valores.get("Yield")
    if rendimiento is None or rendimiento <= 0:
        return None
    deflactor = ipc[anio_base] / ipc[anio]
    fila: dict[str, Any] = {"origen": "ERS", "cultivo": cultivo, "region": region, "anio": anio}
    for categoria, items in CATEGORIAS.items():
        total = Decimal(0)
        for item in items:
            nombres = item.split("|")
            valor = next((valores[n] for n in nombres if n in valores), None)
            if valor is None:
                return None
            total += valor
        fila[COLUMNAS_COSTO[categoria]] = _redondear(
            total * deflactor * ACRES_POR_HECTAREA * BOB_POR_USD
        )
    fila["rendimientoHa"] = _redondear(rendimiento * KG_POR_BUSHEL[cultivo] * ACRES_POR_HECTAREA)
    return fila


def leer_ipc(ruta: Path) -> dict[int, Decimal]:
    with ruta.open(encoding="utf-8") as archivo:
        return {int(f["anio"]): Decimal(f["ipc"]) for f in csv.DictReader(archivo)}


def escribir_csv(filas: list[dict[str, Any]], ruta: Path) -> None:
    salida = io.StringIO()
    escritor = csv.DictWriter(salida, fieldnames=COLUMNAS, lineterminator="\n")
    escritor.writeheader()
    for fila in filas:
        escritor.writerow(
            {k: (format(v, "f") if isinstance(v, Decimal) else v) for k, v in fila.items()}
        )
    ruta.write_text(salida.getvalue(), encoding="utf-8")


def _descargar(destino: Path) -> None:
    with httpx.Client(
        follow_redirects=True, timeout=60, headers={"User-Agent": "servicio-ia"}
    ) as http:
        for archivo, url in FUENTES_ERS.values():
            respuesta = http.get(url)
            respuesta.raise_for_status()
            (destino / archivo).write_bytes(respuesta.content)


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def preparar(origen: Path | None, destino: Path = CARPETA_REFERENCIA) -> Resumen:
    with tempfile.TemporaryDirectory() as temporal:
        carpeta = origen or Path(temporal)
        if origen is None:
            _descargar(carpeta)
        filas: dict[str, list[dict[str, str]]] = {}
        archivos: dict[str, dict[str, str]] = {}
        for cultivo, (archivo, url) in FUENTES_ERS.items():
            ruta = carpeta / archivo
            with ruta.open(encoding="utf-8-sig") as entrada:
                filas[cultivo] = list(csv.DictReader(entrada))
            archivos[cultivo] = {"archivo": archivo, "url": url, "sha256": _sha256(ruta)}

        ipc = leer_ipc(destino / "ipc_eeuu.csv")
        resultado, resumen = transformar(filas, ipc)

    destino.mkdir(parents=True, exist_ok=True)
    escribir_csv(resultado, destino / "campanias_referencia.csv")
    fuentes = {
        "dataset": "USDA ERS, Commodity Costs and Returns (Recent Cost and Returns)",
        "pagina": "https://www.ers.usda.gov/data-products/commodity-costs-and-returns",
        "cita": "U.S. Department of Agriculture, Economic Research Service. "
        "Commodity Costs and Returns data.",
        "licencia": "Publicación del gobierno federal de EE. UU. (dominio público en EE. UU.)",
        "fechaPreparacion": datetime.now(UTC).date().isoformat(),
        "archivos": archivos,
        "ipc": {
            "serie": "BLS CPI-U, CUUR0000SA0, promedio anual (M13)",
            "fuente": "https://api.bls.gov/publicAPI/v2/timeseries/data/",
            "archivo": "ipc_eeuu.csv",
            "anioBase": resumen.anio_base,
        },
        "conversiones": {
            "acresPorHectarea": str(ACRES_POR_HECTAREA),
            "bobPorUsd": str(BOB_POR_USD),
            "kgPorBushel": {k: str(v) for k, v in KG_POR_BUSHEL.items()},
        },
        "filas": dict(resumen.filas_por_cultivo),
        "descartadas": dict(resumen.descartadas_por_cultivo),
    }
    (destino / "fuentes.json").write_text(
        json.dumps(fuentes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return resumen


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--origen", type=Path, help="Carpeta con los CSV del ERS ya descargados")
    opciones = parser.parse_args(argumentos)
    resumen = preparar(opciones.origen)
    print(f"Año base del IPC: {resumen.anio_base}")
    for cultivo in FUENTES_ERS:
        print(
            f"{cultivo}: {resumen.filas_por_cultivo[cultivo]} filas, "
            f"{resumen.descartadas_por_cultivo[cultivo]} descartadas"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
