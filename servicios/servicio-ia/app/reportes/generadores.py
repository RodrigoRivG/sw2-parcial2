"""Generación del PDF y del Excel a partir de las tablas ya aplicadas (spec-reportes.md 2.8).

Funciones puras: documento → bytes. Las celdas se presentan según el tipo del campo, sin
cambiar su valor (RN-14): en el PDF, decimales con separador de miles `.` y decimal `,` y los
mismos decimales del dato; en Excel, números como números.
"""

import io
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import cache
from importlib import resources
from typing import Any

from jinja2 import Environment
from markupsafe import Markup
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from app.reportes.catalogo import Campo, TipoCampo
from app.reportes.plan import Tabla

BOLIVIA = timezone(timedelta(hours=-4))  # sin horario de verano
COLUMNAS_APAISADO = 6
_HOJA_INVALIDA = re.compile(r"[\[\]:*?/\\]")


@dataclass(frozen=True)
class Documento:
    titulo: str
    fecha_generacion: datetime
    tablas: list[Tabla]
    filtros: list[list[str]]  # por tabla, los filtros en palabras
    solicitud: str | None = None
    resumen: str | None = None
    advertencias: list[str] = field(default_factory=list)
    aviso: str = ""
    servicios: list[str] = field(default_factory=list)


# --- presentación de celdas ----------------------------------------------------------------


def _decimal(valor: Any) -> Decimal | None:
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return None


def _miles(numero: Decimal) -> str:
    """`38250.00` → `38.250,00`, con los mismos decimales."""
    signo = "-" if numero < 0 else ""
    entero, _, decimales = format(abs(numero), "f").partition(".")
    grupos = f"{int(entero):,}".replace(",", ".")
    return f"{signo}{grupos},{decimales}" if decimales else f"{signo}{grupos}"


def _fecha_hora(valor: Any) -> datetime | None:
    try:
        momento = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento.astimezone(BOLIVIA) if momento.tzinfo else momento


def _fecha(valor: Any) -> date | None:
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def legible(valor: str) -> str:
    """`MANO_DE_OBRA` → `Mano de obra`."""
    return valor.replace("_", " ").capitalize()


def texto_celda(valor: Any, campo: Campo) -> str:
    if valor is None or valor == "":
        return "—"
    tipo = campo.tipo
    if tipo in (TipoCampo.DECIMAL, TipoCampo.ENTERO) and (numero := _decimal(valor)) is not None:
        return _miles(numero)
    if tipo is TipoCampo.FECHA and (dia := _fecha(valor)):
        return dia.strftime("%d/%m/%Y")
    if tipo is TipoCampo.FECHA_HORA and (momento := _fecha_hora(valor)):
        return momento.strftime("%d/%m/%Y %H:%M")
    if tipo is TipoCampo.BOOLEANO:
        return "Sí" if valor is True or str(valor).lower() == "true" else "No"
    if tipo is TipoCampo.ENUM:
        return legible(str(valor))
    return str(valor)


def _valor_excel(valor: Any, campo: Campo) -> tuple[Any, str | None]:
    """El valor de la celda de Excel y su formato de número."""
    if valor is None or valor == "":
        return None, None
    tipo = campo.tipo
    if tipo in (TipoCampo.DECIMAL, TipoCampo.ENTERO) and (numero := _decimal(valor)) is not None:
        decimales = max(0, -int(numero.as_tuple().exponent))
        return numero, "#,##0" + ("." + "0" * decimales if decimales else "")
    if tipo is TipoCampo.FECHA and (dia := _fecha(valor)):
        return dia, "DD/MM/YYYY"
    if tipo is TipoCampo.FECHA_HORA and (momento := _fecha_hora(valor)):
        return momento.replace(tzinfo=None), "DD/MM/YYYY HH:MM"
    if tipo is TipoCampo.BOOLEANO:
        return ("Sí" if valor is True or str(valor).lower() == "true" else "No"), None
    if tipo is TipoCampo.ENUM:
        return legible(str(valor)), None
    return str(valor), None


# --- PDF ----------------------------------------------------------------------------------


def _css_texto(valor: str) -> Markup:
    """Texto dentro de una cadena CSS: sin entidades HTML (no se decodifican en `<style>`) y
    sin poder cerrar la cadena ni el `<style>`."""
    escapado = "".join(
        c if c.isalnum() or c in " .,-_()%" else f"\\{ord(c):X} " for c in str(valor)
    )
    return Markup(escapado)


@cache
def _plantilla() -> Any:
    carpeta = resources.files("app.reportes") / "plantillas"
    entorno = Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)
    entorno.filters["celda"] = texto_celda
    entorno.filters["css_texto"] = _css_texto
    return entorno.from_string((carpeta / "reporte.html.j2").read_text("utf-8")), (
        carpeta / "estilos.css"
    ).read_text("utf-8")


def html(documento: Documento) -> str:
    plantilla, estilos = _plantilla()
    apaisado = any(len(t.columnas) > COLUMNAS_APAISADO for t in documento.tablas)
    contenido: str = plantilla.render(
        d=documento,
        estilos=estilos,
        apaisado=apaisado,
        fecha=documento.fecha_generacion.astimezone(BOLIVIA).strftime("%d/%m/%Y %H:%M"),
        tablas=list(zip(documento.tablas, documento.filtros, strict=True)),
    )
    return contenido


def generar_pdf(documento: Documento) -> bytes:
    from weasyprint import HTML  # carga Pango solo al generar

    pdf: bytes = HTML(string=html(documento)).write_pdf()
    return pdf


# --- Excel --------------------------------------------------------------------------------


def _nombre_hoja(titulo: str, usados: set[str]) -> str:
    base = _HOJA_INVALIDA.sub(" ", titulo).strip()[:31] or "Tabla"
    nombre, n = base, 2
    while nombre.lower() in usados:
        sufijo = f" ({n})"
        nombre, n = base[: 31 - len(sufijo)] + sufijo, n + 1
    usados.add(nombre.lower())
    return nombre


def _texto(celda: Any, valor: Any) -> None:
    """Un texto nunca se interpreta como fórmula, aunque empiece con `=` (caso borde)."""
    celda.value = valor
    if isinstance(valor, str):
        celda.data_type = "s"


def _ajustar_anchos(hoja: Any, filas: Sequence[Sequence[Any]]) -> None:
    for i in range(max((len(f) for f in filas), default=0)):
        largo = max((len(str(f[i])) for f in filas if i < len(f) and f[i] is not None), default=8)
        hoja.column_dimensions[get_column_letter(i + 1)].width = min(60, max(10, largo + 2))


def generar_xlsx(documento: Documento) -> bytes:
    libro = Workbook()
    libro.remove(libro.active)  # type: ignore[arg-type]
    resumen = libro.create_sheet("Reporte")
    filas_resumen: list[tuple[str, str]] = [
        ("Reporte", documento.titulo),
        ("Generado", documento.fecha_generacion.astimezone(BOLIVIA).strftime("%d/%m/%Y %H:%M")),
    ]
    if documento.solicitud:
        filas_resumen.append(("Solicitud", documento.solicitud))
    for tabla, filtros in zip(documento.tablas, documento.filtros, strict=True):
        detalle = "; ".join(filtros) if filtros else "sin filtros"
        filas_resumen.append((f"Tabla «{tabla.titulo}»", f"{tabla.total_filas} filas ({detalle})"))
    if documento.resumen:
        filas_resumen.append(("Resumen", documento.resumen))
    filas_resumen.extend(("Advertencia", a) for a in documento.advertencias)
    filas_resumen.append(("Aviso", documento.aviso))
    if documento.servicios:
        filas_resumen.append(("Datos de", ", ".join(documento.servicios)))
    for numero_fila, (etiqueta, valor) in enumerate(filas_resumen, start=1):
        resumen.cell(row=numero_fila, column=1, value=etiqueta).font = Font(bold=True)
        celda = resumen.cell(row=numero_fila, column=2)
        _texto(celda, valor)
        celda.alignment = Alignment(wrap_text=True, vertical="top")
    resumen.column_dimensions["A"].width = 28
    resumen.column_dimensions["B"].width = 100

    usados = {"reporte"}
    for tabla in documento.tablas:
        hoja = libro.create_sheet(_nombre_hoja(tabla.titulo, usados))
        for columna, campo in enumerate(tabla.columnas, start=1):
            hoja.cell(row=1, column=columna, value=campo.etiqueta).font = Font(bold=True)
        for numero, fila in enumerate(tabla.filas, start=2):
            for columna, (valor, campo) in enumerate(
                zip(fila, tabla.columnas, strict=True), start=1
            ):
                dato, formato = _valor_excel(valor, campo)
                celda = hoja.cell(row=numero, column=columna)
                _texto(celda, dato)
                if formato:
                    celda.number_format = formato
        hoja.freeze_panes = "A2"
        visibles = [[c.etiqueta for c in tabla.columnas]] + [
            [texto_celda(v, c) for v, c in zip(f, tabla.columnas, strict=True)] for f in tabla.filas
        ]
        _ajustar_anchos(hoja, visibles)

    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()
