"""Qué herramientas MCP ve cada agente y su conversión al formato de Ollama (spec-agentes.md 2.5).

Un modelo de 3B se confunde con muchas herramientas a la vez (AC-02): cada agente ve solo las
suyas y sin `maximo`, que es para el agente de reportes (2.3).
"""

from collections.abc import Iterable, Mapping
from typing import Any

import mcp.types as tipos_mcp

from app.agentes.estado import Agente

POR_AGENTE: dict[Agente, tuple[str, ...]] = {
    "campanias": (
        "listar_parcelas",
        "listar_cultivos",
        "listar_campanias",
        "obtener_campania",
        "obtener_costos_campania",
        "obtener_indicadores_campania",
        "listar_historicos",
        "listar_labores",
        "listar_incidencias",
    ),
    "inventario": ("consultar_estado_inventario", "obtener_insumo", "listar_labores"),
    "fuera_de_alcance": (),
}
OCULTOS = frozenset({"maximo"})


def _limpiar(esquema: Any) -> Any:
    """Sin `title` (ruido para el modelo) y sin los parámetros ocultos."""
    if isinstance(esquema, Mapping):
        limpio = {k: _limpiar(v) for k, v in esquema.items() if k != "title"}
        if isinstance(limpio.get("properties"), dict):
            limpio["properties"] = {
                k: v for k, v in limpio["properties"].items() if k not in OCULTOS
            }
            if "required" in limpio:
                limpio["required"] = [r for r in limpio["required"] if r not in OCULTOS]
        return limpio
    if isinstance(esquema, list):
        return [_limpiar(v) for v in esquema]
    return esquema


def a_ollama(herramienta: tipos_mcp.Tool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": herramienta.name,
            "description": herramienta.description or "",
            "parameters": _limpiar(herramienta.input_schema),
        },
    }


def para_agente(agente: Agente, herramientas: Iterable[tipos_mcp.Tool]) -> list[dict[str, Any]]:
    permitidas = POR_AGENTE[agente]
    por_nombre = {h.name: h for h in herramientas}
    return [a_ollama(por_nombre[n]) for n in permitidas if n in por_nombre]
