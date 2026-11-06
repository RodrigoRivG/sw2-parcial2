"""Plan del reporte: validación y aplicación (spec-reportes.md 1.1, 2.6; historias 1, 3 y 5)."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.reportes.catalogo import FUENTES, TITULOS
from app.reportes.plan import (
    OPERADORES_POR_TIPO,
    Filtro,
    PlanReporte,
    TablaPlan,
    aplicar,
    describir_filtro,
    esquema_json,
    validar,
)

HISTORICOS = [
    {
        "nombreCampania": "Soya verano Norte",
        "nombreParcela": "Lote Norte",
        "nombreCultivo": "Soya",
        "superficieHectareas": "120.0000",
        "fechaFinalizacion": "2026-03-28T18:00:00Z",
        "produccion": "336000.00",
        "costoTotal": "324000.00",
        "rendimientoPorHectarea": "2800.00",
        "costoPorHectarea": "2700.00",
    },
    {
        "nombreCampania": "Soya verano Sur",
        "nombreParcela": "Lote Sur",
        "nombreCultivo": "Soya",
        "superficieHectareas": "85.5000",
        "fechaFinalizacion": "2026-04-05T12:00:00Z",
        "produccion": "205200.00",
        "costoTotal": "239400.00",
        "rendimientoPorHectarea": "2400.00",
        "costoPorHectarea": "2800.00",
    },
    {
        "nombreCampania": "Maíz invierno",
        "nombreParcela": "El Paraíso",
        "nombreCultivo": "Maíz",
        "superficieHectareas": "200.0000",
        "fechaFinalizacion": "2025-09-30T12:00:00Z",
        "produccion": "1000000.00",
        "costoTotal": "440000.00",
        "rendimientoPorHectarea": "5000.00",
        "costoPorHectarea": "2200.00",
    },
    {
        "nombreCampania": "Sin producción",
        "nombreParcela": "Lote Este",
        "nombreCultivo": "Sorgo",
        "superficieHectareas": "10.0000",
        "fechaFinalizacion": "2026-01-10T12:00:00Z",
        "produccion": None,
        "costoTotal": "9000.00",
        "rendimientoPorHectarea": None,
        "costoPorHectarea": "900.00",
    },
]


def _tabla(**datos: Any) -> TablaPlan:
    return TablaPlan.model_validate({"fuente": "CAMPANIAS_FINALIZADAS", **datos})


def _plan(*tablas: dict[str, Any], **datos: Any) -> PlanReporte:
    return PlanReporte.model_validate({"tablas": list(tablas), **datos})


# --- validar -------------------------------------------------------------------------------


def test_plan_valido_sin_errores_y_valores_por_defecto() -> None:
    plan = _plan(
        {
            "fuente": "INVENTARIO",
            "filtros": [{"campo": "stockBajo", "operador": "igual", "valor": True}],
        }
    )

    assert validar(plan) == []
    assert [f.value for f in plan.formatos] == ["PDF"]
    assert plan.incluir_resumen is True and plan.no_atendido == []


@pytest.mark.parametrize(
    ("tabla", "ruta", "texto"),
    [
        ({"fuente": "CLIMA"}, "tablas[0].fuente", "Válidas: PARCELAS"),
        (
            {"fuente": "INVENTARIO", "columnas": ["nombre", "precio"]},
            "tablas[0].columnas[1]",
            "Campos de INVENTARIO",
        ),
        (
            {"fuente": "INVENTARIO", "columnas": ["nombre", "nombre"]},
            "tablas[0].columnas",
            "repetidas",
        ),
        (
            {
                "fuente": "INVENTARIO",
                "filtros": [{"campo": "color", "operador": "igual", "valor": "x"}],
            },
            "tablas[0].filtros[0].campo",
            "no existe",
        ),
        (
            {
                "fuente": "INVENTARIO",
                "filtros": [{"campo": "stock", "operador": "contiene", "valor": "1"}],
            },
            "tablas[0].filtros[0].operador",
            "no aplica a stock",
        ),
        (
            {
                "fuente": "INVENTARIO",
                "filtros": [{"campo": "nombre", "operador": "mayor", "valor": "a"}],
            },
            "tablas[0].filtros[0].operador",
            "Válidos:",
        ),
        (
            {
                "fuente": "INVENTARIO",
                "filtros": [{"campo": "stock", "operador": "mayor", "valor": "mucho"}],
            },
            "tablas[0].filtros[0].valor",
            "debe ser un número",
        ),
        (
            {
                "fuente": "INVENTARIO",
                "filtros": [{"campo": "categoria", "operador": "igual", "valor": "ABONO"}],
            },
            "tablas[0].filtros[0].valor",
            "SEMILLA, FERTILIZANTE, FITOSANITARIO",
        ),
        (
            {
                "fuente": "INVENTARIO",
                "filtros": [{"campo": "stock", "operador": "entre", "valor": [1]}],
            },
            "tablas[0].filtros[0].valor",
            "2 valores",
        ),
        (
            {
                "fuente": "INVENTARIO",
                "filtros": [{"campo": "categoria", "operador": "en", "valor": []}],
            },
            "tablas[0].filtros[0].valor",
            "no vacía",
        ),
        (
            {
                "fuente": "INVENTARIO",
                "filtros": [{"campo": "nombre", "operador": "igual", "valor": None}],
            },
            "tablas[0].filtros[0].valor",
            "Debe tener un valor",
        ),
        (
            {
                "fuente": "LABORES",
                "filtros": [
                    {"campo": "fechaEjecucion", "operador": "mayor", "valor": "31/10/2026"}
                ],
            },
            "tablas[0].filtros[0].valor",
            "31/10/2026",
        ),
        (
            {"fuente": "INVENTARIO", "orden": [{"campo": "precio"}]},
            "tablas[0].orden[0].campo",
            "no existe",
        ),
        ({"fuente": "COSTOS_CAMPANIA"}, "tablas[0].campania", "es de una campaña"),
        (
            {"fuente": "INVENTARIO", "campania": "Soya"},
            "tablas[0].campania",
            "no es de una campaña",
        ),
    ],
)
def test_errores_de_validacion_con_ruta_y_valores_validos(
    tabla: dict[str, Any], ruta: str, texto: str
) -> None:
    errores = validar(_plan(tabla))

    assert [e.campo for e in errores] == [ruta]
    assert texto in errores[0].mensaje


def test_limites_del_esquema() -> None:
    with pytest.raises(ValidationError):
        _plan(*[{"fuente": "PARCELAS"}] * 6)
    with pytest.raises(ValidationError):
        PlanReporte.model_validate({"tablas": []})
    with pytest.raises(ValidationError):
        _plan({"fuente": "PARCELAS", "limite": 501})
    with pytest.raises(ValidationError):
        _plan({"fuente": "PARCELAS"}, formatos=["CSV"])
    with pytest.raises(ValidationError):
        _plan({"fuente": "PARCELAS"}, otro=1)


def test_operadores_por_tipo_cubren_todos_los_tipos() -> None:
    tipos = {c.tipo for f in FUENTES.values() for c in f.campos}
    assert tipos <= set(OPERADORES_POR_TIPO)
    assert set(TITULOS) == set(FUENTES)


# --- aplicar -------------------------------------------------------------------------------


def test_solo_las_columnas_pedidas_en_su_orden_y_valores_sin_cambios() -> None:
    tabla = _tabla(
        columnas=["rendimientoPorHectarea", "nombreParcela"],
        filtros=[{"campo": "nombreCultivo", "operador": "contiene", "valor": "SOYA"}],
        orden=[{"campo": "rendimientoPorHectarea", "sentido": "desc"}],
    )

    resultado = aplicar(tabla, HISTORICOS, total_origen=4)

    assert [c.nombre for c in resultado.columnas] == ["rendimientoPorHectarea", "nombreParcela"]
    assert [c.etiqueta for c in resultado.columnas] == ["Rendimiento (kg/ha)", "Parcela"]
    assert resultado.filas == [["2800.00", "Lote Norte"], ["2400.00", "Lote Sur"]]
    assert (resultado.total_filas, resultado.total_origen) == (2, 4)
    assert resultado.titulo == "Campañas finalizadas"


def test_columnas_y_orden_por_defecto() -> None:
    resultado = aplicar(_tabla(), HISTORICOS, 4)

    assert [c.nombre for c in resultado.columnas] == FUENTES[
        "CAMPANIAS_FINALIZADAS"
    ].columnas_por_defecto
    # finalización descendente
    assert [f[0] for f in resultado.filas] == [
        "Soya verano Sur",
        "Soya verano Norte",
        "Sin producción",
        "Maíz invierno",
    ]


def test_mayor_compara_como_numero_y_vacios_no_cumplen() -> None:
    tabla = _tabla(
        columnas=["nombreParcela"],
        filtros=[{"campo": "costoPorHectarea", "operador": "mayor", "valor": "2500"}],
        orden=[{"campo": "nombreParcela"}],
    )
    sin_rendimiento = _tabla(
        columnas=["nombreParcela"],
        filtros=[{"campo": "rendimientoPorHectarea", "operador": "menor", "valor": 3000}],
    )

    assert aplicar(tabla, HISTORICOS, 4).filas == [["Lote Norte"], ["Lote Sur"]]
    # "900.00" < "2500" como texto sería falso; como número también lo es
    assert [f[0] for f in aplicar(sin_rendimiento, HISTORICOS, 4).filas] == [
        "Lote Sur",
        "Lote Norte",
    ]


def test_orden_y_limite_las_tres_de_mayor_costo_por_hectarea() -> None:
    tabla = _tabla(
        columnas=["nombreParcela", "nombreCultivo", "costoPorHectarea"],
        orden=[{"campo": "costoPorHectarea", "sentido": "desc"}],
        limite=3,
    )

    assert aplicar(tabla, HISTORICOS, 4).filas == [
        ["Lote Sur", "Soya", "2800.00"],
        ["Lote Norte", "Soya", "2700.00"],
        ["El Paraíso", "Maíz", "2200.00"],
    ]


def test_vacios_al_final_en_ambos_sentidos() -> None:
    for sentido in ("asc", "desc"):
        tabla = _tabla(
            columnas=["nombreParcela"],
            orden=[{"campo": "rendimientoPorHectarea", "sentido": sentido}],
        )
        assert aplicar(tabla, HISTORICOS, 4).filas[-1] == ["Lote Este"]


def test_fechas_entre_incluyen_el_ultimo_dia_y_texto_sin_tildes() -> None:
    entre = _tabla(
        columnas=["nombreParcela"],
        filtros=[
            {
                "campo": "fechaFinalizacion",
                "operador": "entre",
                "valor": ["2026-01-01", "2026-03-28"],
            }
        ],
        orden=[{"campo": "nombreParcela"}],
    )
    tildes = _tabla(
        columnas=["nombreParcela"],
        filtros=[{"campo": "nombreCultivo", "operador": "igual", "valor": "maiz"}],
    )
    empieza = _tabla(
        columnas=["nombreParcela"],
        filtros=[{"campo": "nombreParcela", "operador": "empiezaCon", "valor": "lote"}],
    )

    assert aplicar(entre, HISTORICOS, 4).filas == [["Lote Este"], ["Lote Norte"]]
    assert aplicar(tildes, HISTORICOS, 4).filas == [["El Paraíso"]]
    assert len(aplicar(empieza, HISTORICOS, 4).filas) == 3


@pytest.mark.parametrize(
    ("filtro", "esperado"),
    [
        ({"campo": "stockBajo", "operador": "igual", "valor": "sí"}, ["Glifosato"]),
        ({"campo": "stockBajo", "operador": "distinto", "valor": True}, ["Urea", "Semilla"]),
        (
            {"campo": "categoria", "operador": "en", "valor": ["semilla", "fitosanitario"]},
            ["Glifosato", "Semilla"],
        ),
        ({"campo": "fechaUltimaAlerta", "operador": "vacio"}, ["Urea", "Semilla"]),
        ({"campo": "fechaUltimaAlerta", "operador": "noVacio"}, ["Glifosato"]),
        ({"campo": "stock", "operador": "menorIgual", "valor": "20"}, ["Glifosato"]),
        ({"campo": "stock", "operador": "mayorIgual", "valor": "150.5"}, ["Urea", "Semilla"]),
        ({"campo": "nombre", "operador": "distinto", "valor": "urea"}, ["Glifosato", "Semilla"]),
    ],
)
def test_operadores_sobre_inventario(filtro: dict[str, Any], esperado: list[str]) -> None:
    inventario = [
        {
            "nombre": "Glifosato",
            "categoria": "FITOSANITARIO",
            "stock": "20.000",
            "stockBajo": True,
            "fechaUltimaAlerta": "2026-11-02T10:15:00Z",
        },
        {
            "nombre": "Urea",
            "categoria": "FERTILIZANTE",
            "stock": "150.500",
            "stockBajo": False,
            "fechaUltimaAlerta": None,
        },
        {
            "nombre": "Semilla",
            "categoria": "SEMILLA",
            "stock": "2500.000",
            "stockBajo": False,
            "fechaUltimaAlerta": None,
        },
    ]
    tabla = TablaPlan.model_validate(
        {
            "fuente": "INVENTARIO",
            "columnas": ["nombre"],
            "filtros": [filtro],
            "orden": [{"campo": "stock"}],
        }
    )

    assert validar(_plan(tabla.model_dump(by_alias=True))) == []
    assert [f[0] for f in aplicar(tabla, inventario, 3).filas] == esperado


def test_tabla_vacia_y_recorte_a_500() -> None:
    vacia = aplicar(
        _tabla(filtros=[{"campo": "nombreCultivo", "operador": "igual", "valor": "arroz"}]),
        HISTORICOS,
        4,
    )
    muchas = aplicar(
        TablaPlan(fuente="PARCELAS"), [{"nombre": f"P{i:04}"} for i in range(700)], 700
    )

    assert vacia.filas == [] and vacia.total_filas == 0
    assert muchas.total_filas == 500 and muchas.total_origen == 700


def test_describir_filtros_en_palabras() -> None:
    fuente = FUENTES["CAMPANIAS_FINALIZADAS"]

    def describir(**f: Any) -> str:
        return describir_filtro(Filtro.model_validate(f), fuente)

    assert (
        describir(campo="nombreCultivo", operador="contiene", valor="soya")
        == "Cultivo contiene «soya»"
    )
    assert (
        describir(campo="costoPorHectarea", operador="entre", valor=[1, 2])
        == "Costo por ha (Bs/ha) entre «1» y «2»"
    )
    assert (
        describir(campo="nombreCultivo", operador="en", valor=["a", "b"])
        == "Cultivo es uno de: «a», «b»"
    )
    assert describir(campo="produccion", operador="vacio") == "Producción (kg) está vacío"


def test_esquema_json_con_fuentes_y_campos_reales() -> None:
    esquema = esquema_json()
    tabla = esquema["properties"]["tablas"]["items"]["properties"]

    assert tabla["fuente"]["enum"] == list(FUENTES)
    assert "rendimientoPorHectarea" in tabla["columnas"]["items"]["enum"]
    assert "precio" not in tabla["columnas"]["items"]["enum"]
    assert esquema["properties"]["formatos"]["items"]["enum"] == ["PDF", "XLSX"]
