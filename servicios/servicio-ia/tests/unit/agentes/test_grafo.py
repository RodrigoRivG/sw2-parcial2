"""Grafo de agentes con `ModeloGuion` y el servidor MCP real sobre servicios simulados
(spec-agentes.md, historias 1 y 3; 2.5)."""

import json

import pytest
from langgraph.errors import GraphRecursionError

from app.agentes.cifras import SIN_CIFRAS_VERIFICABLES
from app.agentes.estado import MAXIMO_LLAMADAS, MAXIMO_PASOS, EstadoAgente
from app.agentes.grafo import construir_grafo
from app.agentes.herramientas import POR_AGENTE
from app.agentes.nodos import FUERA_DE_ALCANCE, por_palabras_clave
from app.integracion.modelo_lenguaje import ModeloLenguajeNoDisponible
from tests.modelo_guion import ModeloGuion, agente, herramientas, texto
from tests.unit.mcp_server.conftest import Servicios, conectar, ejemplo

INV = "/api/inventario/v1"
G = "/api/gestion/v1"


def _inventario() -> Servicios:
    servicios = Servicios()
    estado = {**ejemplo("estado_inventario"), "total": 1}
    servicios.json(f"{INV}/estado-inventario", estado)
    return servicios


async def consultar(
    modelo: ModeloGuion, servicios: Servicios, pregunta: str, pasos: int = MAXIMO_PASOS
) -> EstadoAgente:
    fallo: Exception | None = None
    async with conectar(servicios) as sesion:
        lista = (await sesion.list_tools()).tools
        grafo = construir_grafo(modelo, sesion, lista)
        try:
            estado: EstadoAgente = await grafo.ainvoke(
                {"pregunta": pregunta, "llamadas": []}, {"recursion_limit": pasos}
            )
        except Exception as error:  # dentro del Client saldría en un ExceptionGroup
            fallo = error
    if fallo is not None:
        raise fallo
    return estado


async def test_pregunta_de_inventario_de_punta_a_punta() -> None:
    modelo = ModeloGuion(
        agente("inventario"),
        herramientas(("consultar_estado_inventario", {"soloStockBajo": True})),
        texto(""),
        texto("Hay 2 insumos con stock bajo. Glifosato tiene 20 litros, igual a su mínimo."),
    )
    servicios = _inventario()

    estado = await consultar(modelo, servicios, "¿Qué insumos están bajo el mínimo?")

    assert estado["agente"] == "inventario"
    assert estado["respuesta"].startswith("Hay 2 insumos con stock bajo.")
    assert estado["cifrasOmitidas"] == 0
    (llamada,) = estado["llamadas"]
    assert llamada["nombre"] == "consultar_estado_inventario"
    assert llamada["error"] is None
    assert llamada["resultado"]["resumen"]["totalStockBajo"] == 2
    assert servicios.parametros()["soloStockBajo"] == "true"

    clasificar, actuar, segundo_actuar, redactar = modelo.pedidos
    assert clasificar.formato is not None and clasificar.herramientas is None
    assert actuar.nombres_herramientas == list(POR_AGENTE["inventario"])
    parametros = actuar.herramientas[0]["function"]["parameters"]  # type: ignore[index]
    assert "maximo" not in parametros["properties"]  # solo lo usa el agente de reportes
    assert segundo_actuar.mensajes[-1]["role"] == "tool"
    assert json.loads(segundo_actuar.mensajes[-1]["content"])["total"] == 1
    assert "Datos consultados" in redactar.mensajes[-1]["content"]
    assert redactar.herramientas is None


async def test_pregunta_de_campanias_usa_herramientas_de_gestion() -> None:
    servicios = Servicios()
    servicios.json(
        f"{G}/campanias/historicos",
        {"items": [ejemplo("historico")], "pagina": 0, "tamanio": 500, "total": 1},
    )
    modelo = ModeloGuion(
        agente("campanias"),
        herramientas(("listar_historicos", {"ordenarPor": "costoPorHectarea"})),
        texto(""),
        texto("La campaña con mayor costo por hectárea fue la de Lote Norte, con 1500.00 Bs/ha."),
    )

    estado = await consultar(
        modelo, servicios, "¿Qué campañas tienen el costo por hectárea más alto?"
    )

    assert estado["agente"] == "campanias"
    assert modelo.pedidos[1].nombres_herramientas == list(POR_AGENTE["campanias"])
    assert estado["cifrasOmitidas"] == 0


async def test_fuera_de_alcance_sin_herramientas() -> None:
    modelo = ModeloGuion(agente("fuera_de_alcance"))
    servicios = Servicios()

    estado = await consultar(modelo, servicios, "¿Quién ganó el partido?")

    assert estado["agente"] == "fuera_de_alcance"
    assert estado["respuesta"] == FUERA_DE_ALCANCE
    assert estado["llamadas"] == []
    assert len(modelo.pedidos) == 1 and servicios.solicitudes == []


async def test_clasificacion_invalida_dos_veces_usa_palabras_clave() -> None:
    modelo = ModeloGuion(
        texto("no es json"),
        texto('{"agente": "clima"}'),
        texto(""),
        texto("No se consultaron datos."),
    )

    estado = await consultar(modelo, Servicios(), "¿Cuánto stock de urea queda?")

    assert estado["agente"] == "inventario"
    assert len(modelo.pedidos) == 4


@pytest.mark.parametrize(
    ("pregunta", "esperado"),
    [
        ("¿Qué fertilizantes hay?", "inventario"),
        ("¿Cuál fue el rendimiento de la campaña de maíz?", "campanias"),
        ("Incidencias de plaga en la parcela norte", "campanias"),
        ("¿Va a llover mañana?", "fuera_de_alcance"),
    ],
)
def test_palabras_clave(pregunta: str, esperado: str) -> None:
    assert por_palabras_clave(pregunta) == esperado


async def test_tope_de_seis_llamadas_y_redacta_con_lo_que_tiene() -> None:
    cuatro = herramientas(*[("consultar_estado_inventario", {})] * 4)
    modelo = ModeloGuion(
        agente("inventario"), cuatro, cuatro, texto("Hay 2 insumos con stock bajo.")
    )
    servicios = _inventario()

    estado = await consultar(modelo, servicios, "¿Qué insumos están bajo el mínimo?")

    assert len(estado["llamadas"]) == MAXIMO_LLAMADAS == 6
    assert len(servicios.solicitudes) == 6
    assert len(modelo.pedidos) == 4  # clasificar, 2 × actuar y redactar: el tercer actuar no llama
    assert estado["respuesta"] == "Hay 2 insumos con stock bajo."


async def test_limite_de_pasos_del_grafo() -> None:
    modelo = ModeloGuion(
        agente("inventario"), herramientas(("consultar_estado_inventario", {})), repetir=True
    )

    with pytest.raises(GraphRecursionError):
        await consultar(modelo, _inventario(), "¿Qué insumos están bajo?", pasos=4)


async def test_herramienta_inexistente_se_reintenta_y_luego_se_ignora() -> None:
    modelo = ModeloGuion(
        agente("inventario"),
        herramientas(("borrar_insumo", {"idInsumo": "x"})),
        herramientas(("listar_parcelas", {})),  # existe, pero no es de este agente
        texto("No pude consultar datos."),
    )
    servicios = Servicios()

    estado = await consultar(modelo, servicios, "¿Qué insumos están bajo el mínimo?")

    assert estado["llamadas"] == []
    assert servicios.solicitudes == []
    assert len(modelo.pedidos) == 4  # el reintento de actuar cuenta como una llamada más


async def test_reintento_valido_se_ejecuta() -> None:
    modelo = ModeloGuion(
        agente("inventario"),
        herramientas(("no_existe", {})),
        herramientas(("consultar_estado_inventario", {})),
        texto(""),
        texto("Hay 2 insumos con stock bajo."),
    )

    estado = await consultar(modelo, _inventario(), "¿Qué insumos están bajo el mínimo?")

    assert [ll["nombre"] for ll in estado["llamadas"]] == ["consultar_estado_inventario"]


async def test_error_de_herramienta_se_informa_y_no_se_inventa_el_dato() -> None:
    servicios = Servicios()
    servicios.json(f"{INV}/estado-inventario", {"codigo": "X"}, estado=503)
    modelo = ModeloGuion(
        agente("inventario"),
        herramientas(("consultar_estado_inventario", {"soloStockBajo": True})),
        texto(""),
        texto(
            "No pude obtener el inventario porque servicio-inventario no está disponible. "
            "Hay 4 insumos con stock bajo."
        ),
    )

    estado = await consultar(modelo, servicios, "¿Qué insumos están bajo el mínimo?")

    (llamada,) = estado["llamadas"]
    assert llamada["error"] == "servicio-inventario no disponible"
    assert llamada["resultado"] is None
    assert modelo.pedidos[2].mensajes[-1]["content"] == "Error: servicio-inventario no disponible"
    redactar = modelo.pedidos[3].mensajes[-1]["content"]
    assert "Consultas que fallaron" in redactar and "servicio-inventario no disponible" in redactar
    assert estado["respuesta"] == (
        "No pude obtener el inventario porque servicio-inventario no está disponible."
    )
    assert estado["cifrasOmitidas"] == 1


async def test_parametros_invalidos_del_modelo_vuelven_como_error() -> None:
    modelo = ModeloGuion(
        agente("inventario"),
        herramientas(("obtener_insumo", {"idInsumo": "glifosato"})),
        texto(""),
        texto("No encontré el insumo."),
    )
    servicios = Servicios()

    estado = await consultar(modelo, servicios, "¿Cuánto glifosato hay?")

    (llamada,) = estado["llamadas"]
    assert llamada["error"] is not None
    assert llamada["error"].startswith(
        "Parámetros inválidos (idInsumo: Input should be a valid UUID"
    )
    assert "pydantic" not in llamada["error"]
    assert servicios.solicitudes == []


async def test_todas_las_cifras_inventadas() -> None:
    modelo = ModeloGuion(agente("inventario"), texto(""), texto("Hay 15 insumos."))

    estado = await consultar(modelo, Servicios(), "¿Cuántos insumos hay?")

    assert estado["respuesta"] == SIN_CIFRAS_VERIFICABLES
    assert estado["cifrasOmitidas"] == 1
    assert "No se consultó ningún dato." in modelo.pedidos[2].mensajes[-1]["content"]


async def test_el_modelo_cae_durante_la_consulta() -> None:
    modelo = ModeloGuion(agente("inventario"), ModeloLenguajeNoDisponible())

    with pytest.raises(ModeloLenguajeNoDisponible):
        await consultar(modelo, Servicios(), "¿Qué insumos están bajo el mínimo?")
