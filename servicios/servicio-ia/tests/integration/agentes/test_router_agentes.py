"""`POST /consultas-agente` y `/api/ia/v1/mcp` (spec-agentes.md 2.7 y 2.10)."""

from collections.abc import Callable
from typing import Any

import httpx
import httpx2
from fastapi.testclient import TestClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from app.agentes.servicio import ServicioAgentes
from app.config import Configuracion
from app.integracion.gateway import ClienteGateway
from app.mcp_server.herramientas import NOMBRES
from app.mcp_server.servidor import crear_servidor_mcp
from tests.conftest import ProveedorClavesLocal, autorizacion, emitir_token
from tests.integration.conftest import esperar_estado_final, esperar_rabbitmq
from tests.modelo_guion import ModeloGuion, agente, herramientas, texto
from tests.unit.mcp_server.conftest import Servicios, TokenFijo, ejemplo

RUTA = "/api/ia/v1/consultas-agente"
RUTA_MCP = "/api/ia/v1/mcp"
TECNICO = autorizacion(emitir_token(["tecnico_campo"]))


def _usar_modelo(cliente: TestClient, modelo: ModeloGuion) -> None:
    """Reemplaza Ollama por el guion y los servicios por respuestas simuladas."""
    servicios = Servicios()
    servicios.json(
        "/api/inventario/v1/estado-inventario", {**ejemplo("estado_inventario"), "total": 1}
    )
    http = httpx.AsyncClient(transport=httpx.MockTransport(servicios))
    gateway = ClienteGateway(http, "http://gateway.prueba", TokenFijo(), 1.0)
    estado = cliente.app.state  # type: ignore[attr-defined]
    estado.modelo_lenguaje = modelo
    estado.servicio_agentes = ServicioAgentes(
        modelo, crear_servidor_mcp(gateway), estado.servicio_trabajos
    )


def test_validacion_y_permisos(cliente: TestClient, cabeceras_gerencia: dict[str, str]) -> None:
    _usar_modelo(cliente, ModeloGuion())

    for cuerpo in ({"pregunta": "  "}, {"pregunta": "x" * 1001}, {"pregunta": "Hola", "otro": 1}):
        respuesta = cliente.post(RUTA, json=cuerpo, headers=cabeceras_gerencia)
        assert respuesta.status_code == 400
        assert respuesta.json()["codigo"] == "DATOS_INVALIDOS"
    assert cliente.post(RUTA, json={"pregunta": "¿Stock?"}).status_code == 401
    respuesta = cliente.post(RUTA, json={"pregunta": "¿Stock?"}, headers=TECNICO)
    assert (respuesta.status_code, respuesta.json()["codigo"]) == (403, "SIN_PERMISO")


def test_ollama_caido_falla_rapido_y_no_afecta_readiness(
    cliente: TestClient, cabeceras_gerencia: dict[str, str]
) -> None:
    _usar_modelo(cliente, ModeloGuion(disponible=False))

    respuesta = cliente.post(
        RUTA, json={"pregunta": "¿Qué insumos hay?"}, headers=cabeceras_gerencia
    )

    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "MODELO_LENGUAJE_NO_DISPONIBLE"
    salud = cliente.get("/salud/readiness").json()
    assert salud["informativos"]["ollama"] == "DOWN"


def test_consulta_de_punta_a_punta_con_rabbitmq(
    crear_cliente: Callable[..., TestClient],
    configuracion_infra: Callable[..., Configuracion],
    cabeceras_gerencia: dict[str, str],
) -> None:
    cliente = crear_cliente(configuracion=configuracion_infra())
    esperar_rabbitmq(cliente)
    _usar_modelo(
        cliente,
        ModeloGuion(
            agente("inventario"),
            herramientas(("consultar_estado_inventario", {"soloStockBajo": True})),
            texto(""),
            texto("Hay 2 insumos con stock bajo. Glifosato tiene 20 litros."),
        ),
    )

    creado = cliente.post(
        RUTA, json={"pregunta": " ¿Qué insumos están bajo el mínimo? "}, headers=cabeceras_gerencia
    )

    assert creado.status_code == 202
    assert creado.headers["Location"].endswith(creado.json()["idTrabajo"])
    trabajo = esperar_estado_final(cliente, creado.json()["idTrabajo"], cabeceras_gerencia)
    assert trabajo["estado"] == "COMPLETADO", trabajo
    resultado: dict[str, Any] = trabajo["resultado"]
    assert resultado["pregunta"] == "¿Qué insumos están bajo el mínimo?"
    assert resultado["agente"] == "inventario"
    assert resultado["respuesta"] == "Hay 2 insumos con stock bajo. Glifosato tiene 20 litros."
    assert resultado["herramientas"][0]["nombre"] == "consultar_estado_inventario"
    assert resultado["datos"][0]["resultado"]["resumen"]["totalStockBajo"] == 2
    assert resultado["cifrasOmitidas"] == 0


def test_modelo_que_cae_durante_la_consulta_deja_el_trabajo_fallido(
    crear_cliente: Callable[..., TestClient],
    configuracion_infra: Callable[..., Configuracion],
    cabeceras_gerencia: dict[str, str],
) -> None:
    from app.integracion.modelo_lenguaje import ModeloLenguajeNoDisponible

    cliente = crear_cliente(configuracion=configuracion_infra())
    esperar_rabbitmq(cliente)
    _usar_modelo(cliente, ModeloGuion(ModeloLenguajeNoDisponible()))

    creado = cliente.post(RUTA, json={"pregunta": "¿Qué insumos hay?"}, headers=cabeceras_gerencia)
    trabajo = esperar_estado_final(cliente, creado.json()["idTrabajo"], cabeceras_gerencia)

    assert trabajo["estado"] == "FALLIDO"
    assert trabajo["error"]["codigo"] == "MODELO_LENGUAJE_NO_DISPONIBLE"


# --- /api/ia/v1/mcp -------------------------------------------------------------------------


def _mcp(cliente: TestClient, cabeceras: dict[str, str]) -> tuple[list[str], Any]:
    """Cliente MCP del SDK por *streamable HTTP*, en el mismo bucle de eventos que la app."""
    cliente.app.state.proveedor_claves = ProveedorClavesLocal()  # type: ignore[attr-defined]

    async def usar() -> tuple[list[str], Any]:
        transporte = httpx2.ASGITransport(app=cliente.app)
        async with (
            httpx2.AsyncClient(transport=transporte, headers=cabeceras) as http,
            Client(
                streamable_http_client(f"http://servicio-ia{RUTA_MCP}", http_client=http)
            ) as mcp,
        ):
            nombres = [h.name for h in (await mcp.list_tools()).tools]
            resultado = await mcp.call_tool("listar_cultivos", {})
            return nombres, resultado

    return cliente.portal.call(usar)  # type: ignore[union-attr]


def test_mcp_por_http_para_gerencia(
    cliente: TestClient, cabeceras_gerencia: dict[str, str]
) -> None:
    nombres, resultado = _mcp(cliente, cabeceras_gerencia)

    assert sorted(nombres) == sorted(NOMBRES)
    # Keycloak y el gateway de los tests no existen: la herramienta informa el error (el token de
    # la cuenta de servicio falla primero) sin romper la sesión.
    assert resultado.is_error
    assert "keycloak no disponible" in resultado.content[0].text


def test_mcp_sin_token_o_sin_rol(cliente: TestClient) -> None:
    cliente.app.state.proveedor_claves = ProveedorClavesLocal()  # type: ignore[attr-defined]
    cuerpo = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

    sin_token = cliente.post(RUTA_MCP, json=cuerpo)
    sin_rol = cliente.post(RUTA_MCP, json=cuerpo, headers=TECNICO)
    token_invalido = cliente.post(RUTA_MCP, json=cuerpo, headers=autorizacion("x.y.z"))

    assert (sin_token.status_code, sin_token.json()["codigo"]) == (401, "NO_AUTENTICADO")
    assert (sin_rol.status_code, sin_rol.json()["codigo"]) == (403, "SIN_PERMISO")
    assert token_invalido.status_code == 401
    assert sin_token.headers["X-Correlation-Id"] == sin_token.json()["idCorrelacion"]
