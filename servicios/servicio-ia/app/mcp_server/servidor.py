"""Servidor MCP con las herramientas de solo lectura (spec-agentes.md 2.3).

Se crea una vez en el `lifespan`. Los agentes lo usan con el transporte en memoria y se
publica por HTTP en `/api/ia/v1/mcp` para gerencia (`mcp_server/http.py`).
"""

import inspect

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from app.mcp_server.herramientas import NOMBRES, HerramientasLectura, Lector

INSTRUCCIONES = (
    "Herramientas de solo lectura sobre parcelas, cultivos, campañas, costos, indicadores, "
    "inventario, labores e incidencias del sistema agrícola. Los decimales vienen como texto. "
    "Los listados traen como máximo 50 elementos, con total y truncado."
)


def crear_servidor_mcp(lector: Lector) -> MCPServer:
    servidor = MCPServer("servicio-ia", instructions=INSTRUCCIONES)
    herramientas = HerramientasLectura(lector)
    solo_lectura = ToolAnnotations(read_only_hint=True, destructive_hint=False)
    for nombre in NOMBRES:
        funcion = getattr(herramientas, nombre)
        servidor.add_tool(
            funcion,
            name=nombre,
            description=inspect.cleandoc(funcion.__doc__ or ""),
            annotations=solo_lectura,
        )
    return servidor
