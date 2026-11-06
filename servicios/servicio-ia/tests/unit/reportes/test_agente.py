"""Agente de reportes con `ModeloGuion` y el servidor MCP real sobre servicios simulados
(spec-reportes.md, historias 1, 3 y 5; 2.7)."""

import json
from datetime import date
from typing import Any

import httpx
import pytest

from app.comun.errores import ErrorAplicacion
from app.integracion.modelo_lenguaje import ModeloLenguajeNoDisponible
from app.reportes.agente import SIN_REGISTROS, EstadoReporte, construir_grafo, mensaje_plan
from app.reportes.plan import FormatoReporte, PlanReporte
from tests.modelo_guion import ModeloGuion, plan_en_dos_pasos, texto
from tests.unit.mcp_server.conftest import Servicios, conectar, ejemplo
from tests.unit.reportes.test_fuentes import C1, INV, G, _pagina, _servicios

HOY = date(2026, 11, 6)
SOYA_NORTE = {
    **ejemplo("historico"),
    "idCampania": C1,
    "nombreParcela": "Lote Norte",
    "rendimientoPorHectarea": "2800.00",
    "costoPorHectarea": "2700.00",
}
SOYA_SUR = {
    **ejemplo("historico"),
    "idCampania": "x2",
    "nombreParcela": "Lote Sur",
    "rendimientoPorHectarea": "2400.00",
    "costoPorHectarea": "2800.00",
}
MAIZ = {
    **ejemplo("historico"),
    "idCampania": "x3",
    "nombreParcela": "El Paraíso",
    "nombreCultivo": "Maíz",
    "rendimientoPorHectarea": "5000.00",
    "costoPorHectarea": "2200.00",
}


def _plan(*tablas: dict[str, Any], **datos: Any) -> dict[str, Any]:
    base = {
        "fuente": "",
        "titulo": None,
        "columnas": [],
        "filtros": [],
        "orden": [],
        "limite": None,
        "campania": None,
    }
    return {
        "titulo": "Reporte",
        "formatos": ["PDF"],
        "incluirResumen": True,
        "tablas": [{**base, **t} for t in tablas],
        "noAtendido": [],
        **datos,
    }


def _con_historicos() -> Servicios:
    servicios = _servicios()
    servicios.json(f"{G}/campanias/historicos", _pagina([SOYA_NORTE, SOYA_SUR, MAIZ]))
    return servicios


async def ejecutar(
    modelo: ModeloGuion,
    servicios: Servicios,
    texto_solicitud: str | None = None,
    plan: dict[str, Any] | None = None,
    formatos: list[str] | None = None,
) -> EstadoReporte:
    entrada: EstadoReporte = {
        "texto": texto_solicitud,
        "plan_dado": plan is not None,
        "formatos": [FormatoReporte(f) for f in formatos] if formatos else None,
    }
    if plan is not None:
        entrada["plan"] = PlanReporte.model_validate(plan)
    fallo: Exception | None = None
    async with conectar(servicios) as sesion:
        try:
            estado: EstadoReporte = await construir_grafo(modelo, sesion, HOY).ainvoke(entrada)
        except Exception as error:  # dentro del Client saldría en un ExceptionGroup
            fallo = error
    if fallo is not None:
        raise fallo
    return estado


async def test_dos_columnas_de_soya_ordenadas_y_resumen_verificado() -> None:
    plan = _plan(
        {
            "fuente": "CAMPANIAS_FINALIZADAS",
            "columnas": ["nombreParcela", "rendimientoPorHectarea"],
            "filtros": [{"campo": "nombreCultivo", "operador": "contiene", "valor": "soya"}],
            "orden": [{"campo": "rendimientoPorHectarea", "sentido": "desc"}],
        },
        formatos=["XLSX"],
    )
    modelo = ModeloGuion(
        *plan_en_dos_pasos(plan),
        texto(
            "La de mayor rendimiento fue Lote Norte con 2800.00 kg/ha. El promedio fue 2600 kg/ha."
        ),
    )

    estado = await ejecutar(
        modelo, _con_historicos(), "Tabla con parcela y rendimiento de soya en Excel"
    )

    (tabla,) = estado["tablas"]
    assert [c.nombre for c in tabla.columnas] == ["nombreParcela", "rendimientoPorHectarea"]
    assert tabla.filas == [["Lote Norte", "2800.00"], ["Lote Sur", "2400.00"]]
    assert estado["plan"].formatos == [FormatoReporte.XLSX]
    assert estado["resumen"] == "La de mayor rendimiento fue Lote Norte con 2800.00 kg/ha."
    assert estado["cifrasOmitidas"] == 1
    fuentes, interpretar, redactar = modelo.pedidos
    assert "Fuentes disponibles" in fuentes.mensajes[0]["content"]
    assert interpretar.formato is not None
    assert "CAMPANIAS_FINALIZADAS" in interpretar.mensajes[0]["content"]
    assert "`INVENTARIO`" not in interpretar.mensajes[0]["content"]
    # el esquema del plan solo admite los campos de la fuente elegida
    tabla = interpretar.formato["properties"]["tablas"]["items"]["properties"]
    assert "stock" not in tabla["columnas"]["items"]["enum"]
    assert "rendimientoPorHectarea" in tabla["columnas"]["items"]["enum"]
    assert "Lote Norte" in redactar.mensajes[-1]["content"]


async def test_formatos_de_la_solicitud_prevalecen() -> None:
    plan = _plan(
        {
            "fuente": "INVENTARIO",
            "filtros": [{"campo": "stockBajo", "operador": "igual", "valor": True}],
        },
        formatos=["PDF", "XLSX"],
    )
    modelo = ModeloGuion(*plan_en_dos_pasos(plan), texto("Glifosato está bajo el mínimo."))

    estado = await ejecutar(
        modelo, _servicios(), "Insumos con stock bajo en PDF y Excel", formatos=["PDF"]
    )

    assert estado["plan"].formatos == [FormatoReporte.PDF]
    assert estado["tablas"][0].filas[0][0] == "Glifosato"


async def test_campania_por_nombre_con_dos_tablas() -> None:
    servicios = _servicios()
    servicios.json(f"{G}/campanias/{C1}/costos", {**ejemplo("costos"), "total": 1})
    plan = _plan(
        {"fuente": "SUBTOTALES_CAMPANIA", "campania": "soya VERANO 2026"},
        {"fuente": "COSTOS_CAMPANIA", "campania": "soya VERANO 2026"},
        incluirResumen=False,
    )

    estado = await ejecutar(
        ModeloGuion(*plan_en_dos_pasos(plan)), servicios, "Costos de la campaña Soya verano 2026"
    )

    assert estado["ids_campania"] == {0: C1, 1: C1}
    assert len(estado["tablas"][0].filas) == 4 and estado["tablas"][1].filas[0][-1] == "1500.00"
    assert estado["resumen"] is None
    costos = [s for s in servicios.solicitudes if s.url.path.endswith("/costos")]
    assert costos and all(s.url.path == f"{G}/campanias/{C1}/costos" for s in costos)


@pytest.mark.parametrize(
    ("nombre", "motivo"), [("Trigo invierno", "ninguna"), ("Campaña", "varias")]
)
async def test_campania_no_identificada_con_parecidas(nombre: str, motivo: str) -> None:
    servicios = _servicios()
    otra = {**ejemplo("campania"), "id": "otra", "nombre": "Campaña de maíz"}
    servicios.json(
        f"{G}/campanias",
        _pagina([{**ejemplo("campania"), "id": C1, "nombre": "Campaña de soya"}, otra]),
    )
    plan = _plan({"fuente": "COSTOS_CAMPANIA", "campania": nombre})

    with pytest.raises(ErrorAplicacion) as error:
        await ejecutar(ModeloGuion(*plan_en_dos_pasos(plan)), servicios, f"Costos de {nombre}")

    assert error.value.codigo == "CAMPANIA_NO_IDENTIFICADA"
    assert motivo in error.value.mensaje and "Campaña de soya" in error.value.mensaje


async def test_calculo_pedido_se_informa_y_se_muestran_los_datos() -> None:
    plan = _plan(
        {"fuente": "CAMPANIAS_FINALIZADAS", "columnas": ["nombreParcela", "costoPorHectarea"]},
        noAtendido=["el costo promedio por hectárea"],
    )
    modelo = ModeloGuion(
        *plan_en_dos_pasos(plan), texto("Lote Sur tuvo el costo más alto: 2800.00 Bs/ha.")
    )

    estado = await ejecutar(modelo, _con_historicos(), "El costo promedio por hectárea")

    (advertencia,) = estado["advertencias"]
    assert advertencia["codigo"] == "CALCULO_NO_PERMITIDO"
    assert "el costo promedio por hectárea" in advertencia["mensaje"]
    assert len(estado["tablas"][0].filas) == 3


async def test_sin_fuentes_o_sin_tablas_es_reporte_no_soportado() -> None:
    sin_tablas = {**_plan(), "tablas": [], "noAtendido": ["el clima de mañana"]}

    with pytest.raises(ErrorAplicacion) as sin_fuentes:
        await ejecutar(ModeloGuion(texto('{"fuentes": []}')), _servicios(), "El clima de mañana")
    with pytest.raises(ErrorAplicacion) as vacio:
        await ejecutar(
            ModeloGuion(texto('{"fuentes": ["PARCELAS"]}'), texto(json.dumps(sin_tablas))),
            _servicios(),
            "El clima de mañana",
        )

    assert sin_fuentes.value.codigo == vacio.value.codigo == "REPORTE_NO_SOPORTADO"
    assert "inventario de insumos" in sin_fuentes.value.mensaje
    assert "el clima de mañana" in vacio.value.mensaje


async def test_plan_invalido_se_corrige_una_vez() -> None:
    malo = _plan({"fuente": "INVENTARIO", "columnas": ["nombre", "precio"]})
    bueno = _plan({"fuente": "INVENTARIO", "columnas": ["nombre", "stock"]}, incluirResumen=False)
    modelo = ModeloGuion(*plan_en_dos_pasos(malo), texto(json.dumps(bueno)))

    estado = await ejecutar(modelo, _servicios(), "Insumos con su precio")

    assert [c.nombre for c in estado["tablas"][0].columnas] == ["nombre", "stock"]
    correccion = modelo.pedidos[2].mensajes[-1]["content"]
    assert "tablas[0].columnas[1]" in correccion and "Campos de INVENTARIO" in correccion


async def test_plan_invalido_dos_veces() -> None:
    malo = _plan({"fuente": "INVENTARIO", "columnas": ["precio"]})
    modelo = ModeloGuion(
        texto('{"fuentes": ["INVENTARIO"]}'), texto("no es json"), texto(json.dumps(malo))
    )

    with pytest.raises(ErrorAplicacion) as error:
        await ejecutar(modelo, _servicios(), "Insumos con su precio")

    assert error.value.codigo == "REPORTE_NO_SOPORTADO" and "precio" in error.value.mensaje


async def test_sin_registros_no_llama_al_modelo_para_el_resumen() -> None:
    plan = _plan(
        {
            "fuente": "INVENTARIO",
            "filtros": [{"campo": "nombre", "operador": "igual", "valor": "x"}],
        }
    )
    modelo = ModeloGuion(*plan_en_dos_pasos(plan))

    estado = await ejecutar(modelo, _servicios(), "Insumo x")

    assert estado["tablas"][0].filas == [] and estado["resumen"] == SIN_REGISTROS
    assert len(modelo.pedidos) == 2  # fuentes y plan; el resumen no llama al modelo


def test_ajustes_deterministas_del_plan_del_modelo() -> None:
    from app.reportes.agente import ajustar
    from app.reportes.catalogo import FUENTES

    nombre_maiz = {"campo": "nombre", "operador": "contiene", "valor": "Maíz invierno"}
    datos = ajustar(
        {
            "noAtendido": ["x" * 400],
            "tablas": [
                {"fuente": "INVENTARIO", "columnas": FUENTES["INVENTARIO"].nombres},
                {"fuente": "INDICADORES_CAMPANIA", "filtros": [nombre_maiz], "campania": None},
                {"fuente": "COSTOS_CAMPANIA", "campania": "Soya", "filtros": [nombre_maiz]},
            ],
        }
    )

    assert len(datos["noAtendido"][0]) == 300
    assert datos["tablas"][0]["columnas"] == []
    assert datos["tablas"][1]["campania"] == "Maíz invierno"
    assert datos["tablas"][1]["filtros"] == [] and datos["tablas"][2]["filtros"] == []


async def test_ninguna_fuente_elegida() -> None:
    with pytest.raises(ErrorAplicacion) as error:
        await ejecutar(ModeloGuion(texto("no es json")), _servicios(), "Hola")

    assert error.value.codigo == "REPORTE_NO_SOPORTADO"


async def test_plan_ya_armado_sin_modelo_disponible() -> None:
    plan = _plan({"fuente": "INVENTARIO"})
    modelo = ModeloGuion(ModeloLenguajeNoDisponible())

    estado = await ejecutar(modelo, _servicios(), plan=plan)

    assert estado["resumen"] is None
    assert [a["codigo"] for a in estado["advertencias"]] == ["RESUMEN_NO_DISPONIBLE"]
    assert len(modelo.pedidos) == 1  # solo el resumen: el plan no se interpreta


async def test_texto_con_modelo_caido() -> None:
    with pytest.raises(ModeloLenguajeNoDisponible):
        await ejecutar(ModeloGuion(ModeloLenguajeNoDisponible()), _servicios(), "Insumos")


async def test_servicio_caido_es_dependencia_no_disponible() -> None:
    servicios = Servicios()
    servicios.json(f"{INV}/estado-inventario", {"codigo": "X"}, estado=503)

    with pytest.raises(ErrorAplicacion) as error:
        await ejecutar(ModeloGuion(), servicios, plan=_plan({"fuente": "INVENTARIO"}))

    assert error.value.codigo == "DEPENDENCIA_NO_DISPONIBLE"


async def test_datos_recortados_se_advierten() -> None:
    servicios = _servicios()
    servicios.rutas[f"{G}/campanias/historicos"] = lambda _: httpx.Response(
        200, json={"items": [SOYA_NORTE], "pagina": 0, "tamanio": 500, "total": 734}
    )

    estado = await ejecutar(
        ModeloGuion(texto("Lote Norte rindió 2800.00 kg/ha.")),
        servicios,
        plan=_plan({"fuente": "CAMPANIAS_FINALIZADAS"}),
    )

    (advertencia,) = estado["advertencias"]
    assert advertencia["codigo"] == "DATOS_RECORTADOS" and "734" in advertencia["mensaje"]


def test_mensaje_de_sistema_con_catalogo_fecha_y_ejemplos() -> None:
    mensaje = mensaje_plan(HOY)

    assert "2026-11-06" in mensaje and "2026-01-01" in mensaje
    assert (
        "`LABORES`" in mensaje
        and "`rendimientoPorHectarea` (Rendimiento (kg/ha); decimal)" in mensaje
    )
    assert "uno de PLANIFICADA/EN_CURSO/FINALIZADA" in mensaje
    assert "{catalogo}" not in mensaje and "<AÑO>" not in mensaje
