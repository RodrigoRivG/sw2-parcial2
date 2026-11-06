"""Servidor MCP real sobre `ClienteGateway` con los servicios simulados (`httpx.MockTransport`)."""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from mcp import Client

from app.integracion.gateway import ClienteGateway
from app.integracion.token_servicio import TokenCuentaServicio
from app.mcp_server.servidor import crear_servidor_mcp

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "servicios"
Respuesta = Callable[[httpx.Request], httpx.Response]


def ejemplo(nombre: str) -> dict[str, Any]:
    datos: dict[str, Any] = json.loads((FIXTURES / f"{nombre}.json").read_text(encoding="utf-8"))
    return datos


class TokenFijo(TokenCuentaServicio):
    def __init__(self) -> None:
        pass

    async def obtener(self) -> str:
        return "token-servicio"

    def invalidar(self) -> None:
        pass


class Servicios:
    """Responde por ruta exacta; registra cada solicitud recibida."""

    def __init__(self) -> None:
        self.rutas: dict[str, Respuesta] = {}
        self.solicitudes: list[httpx.Request] = []

    def json(self, ruta: str, cuerpo: Any, estado: int = 200) -> None:
        self.rutas[ruta] = lambda _: httpx.Response(estado, json=cuerpo)

    def __call__(self, solicitud: httpx.Request) -> httpx.Response:
        self.solicitudes.append(solicitud)
        respuesta = self.rutas.get(solicitud.url.path)
        if respuesta is None:
            return httpx.Response(404, json={"codigo": "RUTA_NO_ENCONTRADA"})
        return respuesta(solicitud)

    def parametros(self, indice: int = -1) -> dict[str, str]:
        return dict(self.solicitudes[indice].url.params)


@asynccontextmanager
async def conectar(servicios: Servicios) -> AsyncIterator[Client]:
    async with httpx.AsyncClient(transport=httpx.MockTransport(servicios)) as http:
        gateway = ClienteGateway(http, "http://gateway.prueba", TokenFijo(), tiempo_limite=1.0)
        async with Client(crear_servidor_mcp(gateway)) as cliente:
            yield cliente


async def llamar(cliente: Client, nombre: str, argumentos: dict[str, Any] | None = None) -> Any:
    """El resultado estructurado; falla el test si la herramienta devolvió error."""
    resultado = await cliente.call_tool(nombre, argumentos or {})
    assert not resultado.is_error, resultado.content
    return resultado.structured_content


async def error(cliente: Client, nombre: str, argumentos: dict[str, Any] | None = None) -> str:
    """El texto del error de herramienta (`isError`)."""
    resultado = await cliente.call_tool(nombre, argumentos or {})
    assert resultado.is_error
    texto: str = resultado.content[0].text  # type: ignore[union-attr]
    return texto
