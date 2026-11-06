"""PDF y Excel (spec-reportes.md 2.8; Historia 5; CE-REP-03)."""

import io
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from openpyxl import load_workbook
from pypdf import PdfReader

from app.reportes.catalogo import FUENTES
from app.reportes.generadores import Documento, generar_pdf, generar_xlsx, texto_celda
from app.reportes.plan import Tabla, TablaPlan, aplicar

FILAS = [
    {
        "nombreCampania": "Soya verano Ñandú",
        "nombreParcela": "Lote Norte",
        "nombreCultivo": "Soya",
        "superficieHectareas": "120.0000",
        "fechaFinalizacion": "2026-03-28T18:00:00Z",
        "produccion": "336000.00",
        "costoTotal": "38250.00",
        "rendimientoPorHectarea": "2800.00",
        "costoPorHectarea": "1530.4567",
        "duracionDias": 133,
        "fechaInicio": "2025-11-10",
    },
    {
        "nombreCampania": '=HYPERLINK("http://x")',
        "nombreParcela": "Lote Sur",
        "nombreCultivo": "Maíz",
        "superficieHectareas": "85.5000",
        "fechaFinalizacion": None,
        "produccion": None,
        "costoTotal": "239400.00",
        "rendimientoPorHectarea": None,
        "costoPorHectarea": "2800.00",
        "duracionDias": 90,
        "fechaInicio": "2025-11-15",
    },
]


def _tabla(columnas: list[str]) -> Tabla:
    plan = TablaPlan.model_validate({"fuente": "CAMPANIAS_FINALIZADAS", "columnas": columnas})
    return aplicar(plan, FILAS, total_origen=2)


def _documento(*tablas: Tabla, **datos: Any) -> Documento:
    valores: dict[str, Any] = {
        "titulo": "Campañas de soya y maíz",
        "fecha_generacion": datetime(2026, 11, 6, 16, 0, tzinfo=UTC),
        "tablas": list(tablas),
        "filtros": [["Cultivo contiene «soya»"] for _ in tablas],
        "solicitud": "Quiero las campañas con año y costo",
        "resumen": "La campaña con mayor costo fue Lote Sur.",
        "advertencias": ["El sistema no calcula promedios."],
        "aviso": "Las tablas son datos de los servicios sin cambios.",
        "servicios": ["servicio-gestion"],
    }
    valores.update(datos)
    return Documento(**valores)


def _texto_pdf(contenido: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(contenido)).pages)


def test_celdas_con_formato_de_lectura_sin_redondear() -> None:
    campo = FUENTES["CAMPANIAS_FINALIZADAS"].campo

    assert texto_celda("38250.00", campo("costoTotal")) == "38.250,00"  # type: ignore[arg-type]
    assert texto_celda("1530.4567", campo("costoPorHectarea")) == "1.530,4567"  # type: ignore[arg-type]
    assert texto_celda(133, campo("duracionDias")) == "133"  # type: ignore[arg-type]
    assert texto_celda("2025-11-10", campo("fechaInicio")) == "10/11/2025"  # type: ignore[arg-type]
    assert texto_celda("2026-03-28T18:00:00Z", campo("fechaFinalizacion")) == "28/03/2026 14:00"  # type: ignore[arg-type]
    assert texto_celda(None, campo("produccion")) == "—"  # type: ignore[arg-type]
    estado = FUENTES["CAMPANIAS"].campo("estado")
    assert texto_celda("EN_CURSO", estado) == "En curso"  # type: ignore[arg-type]
    stock_bajo = FUENTES["INVENTARIO"].campo("stockBajo")
    assert texto_celda(True, stock_bajo) == "Sí"  # type: ignore[arg-type]


def test_pdf_con_tildes_solo_las_columnas_del_plan_y_textos() -> None:
    contenido = generar_pdf(_documento(_tabla(["nombreParcela", "costoTotal"])))

    assert contenido.startswith(b"%PDF")
    texto = _texto_pdf(contenido)
    for esperado in (
        "Campañas de soya y maíz",
        "Parcela",
        "Costo total (Bs)",
        "38.250,00",
        "239.400,00",
        "Lote Sur",
        "Redactado por un modelo de lenguaje",
        "El sistema no calcula promedios.",
        "Cultivo contiene «soya»",
        "Datos de: servicio-gestion.",
    ):
        assert esperado in texto, esperado
    assert "Rendimiento" not in texto and "Ñandú" not in texto
    pagina = PdfReader(io.BytesIO(contenido)).pages[0]
    assert pagina.mediabox.width < pagina.mediabox.height  # vertical


def test_pdf_apaisado_con_muchas_columnas_y_tabla_vacia() -> None:
    columnas = FUENTES["CAMPANIAS_FINALIZADAS"].columnas_por_defecto  # 9 columnas
    vacia = aplicar(
        TablaPlan.model_validate(
            {
                "fuente": "INVENTARIO",
                "filtros": [{"campo": "nombre", "operador": "igual", "valor": "x"}],
            }
        ),
        [],
        0,
    )

    contenido = generar_pdf(_documento(_tabla(columnas), vacia, resumen=None, advertencias=[]))

    pagina = PdfReader(io.BytesIO(contenido)).pages[0]
    assert pagina.mediabox.width > pagina.mediabox.height
    texto = _texto_pdf(contenido)
    assert "No se encontraron registros para los filtros indicados." in texto
    assert "Ñandú" in texto and "Resumen" not in texto


def test_xlsx_con_hoja_de_reporte_y_numeros_como_numeros() -> None:
    tabla = _tabla(
        ["nombreCampania", "costoPorHectarea", "fechaInicio", "fechaFinalizacion", "produccion"]
    )

    libro = load_workbook(io.BytesIO(generar_xlsx(_documento(tabla, tabla))))

    assert libro.sheetnames == ["Reporte", "Campañas finalizadas", "Campañas finalizadas (2)"]
    reporte = {f[0]: f[1] for f in libro["Reporte"].iter_rows(values_only=True)}
    assert reporte["Reporte"] == "Campañas de soya y maíz"
    assert reporte["Resumen"] == "La campaña con mayor costo fue Lote Sur."
    assert "Cultivo contiene «soya»" in reporte["Tabla «Campañas finalizadas»"]
    hoja = libro["Campañas finalizadas"]
    assert [c.value for c in hoja[1]] == [
        "Campaña",
        "Costo por ha (Bs/ha)",
        "Inicio",
        "Finalización",
        "Producción (kg)",
    ]
    assert hoja.freeze_panes == "A2"
    costo = hoja["B2"]
    assert Decimal(str(costo.value)) == Decimal("1530.4567") and costo.number_format == "#,##0.0000"
    assert hoja["E2"].value == 336000 and hoja["E2"].number_format == "#,##0.00"
    assert hoja["C2"].value.date() == date(2025, 11, 10)
    assert hoja["D2"].value == datetime(2026, 3, 28, 14, 0)  # hora de Bolivia
    assert hoja["E3"].value is None and hoja["D3"].value is None
    # un texto con forma de fórmula queda como texto
    formula = hoja["A3"]
    assert formula.value == '=HYPERLINK("http://x")' and formula.data_type == "s"


def _fuentes_pdf(contenido: bytes) -> set[str]:
    nombres = set()
    for pagina in PdfReader(io.BytesIO(contenido)).pages:
        for fuente in (pagina["/Resources"].get("/Font") or {}).values():
            nombres.add(str(fuente.get_object()["/BaseFont"]))
    return nombres


def test_pdf_usa_dejavu_sans_y_un_titulo_no_rompe_los_estilos() -> None:
    titulo = 'Reporte "raro" </style><h1>x</h1> \\ fin'

    contenido = generar_pdf(_documento(_tabla(["nombreParcela"]), titulo=titulo))

    fuentes = _fuentes_pdf(contenido)
    assert any("DejaVu-Sans" in f for f in fuentes)
    assert not any("Serif" in f for f in fuentes), fuentes
    texto = _texto_pdf(contenido)
    assert 'Reporte "raro" </style><h1>x</h1>' in texto  # se muestra como texto, no como HTML


def test_filtros_se_describen_como_se_muestran_las_celdas() -> None:
    from app.reportes.plan import Filtro, describir_filtro

    inventario = FUENTES["INVENTARIO"]
    stock_bajo = Filtro(campo="stockBajo", operador="igual", valor=True)
    categoria = Filtro(campo="categoria", operador="en", valor=["SEMILLA", "fitosanitario"])

    assert describir_filtro(stock_bajo, inventario) == "Stock bajo es «Sí»"
    assert (
        describir_filtro(categoria, inventario) == "Categoría es uno de: «Semilla», «Fitosanitario»"
    )
