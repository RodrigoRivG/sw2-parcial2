"""Grafo de LangGraph de los agentes conversacionales (spec-agentes.md 2.5, RQ-AGE-02)."""

from collections.abc import Iterable
from typing import Any

import mcp.types as tipos_mcp
from langgraph.graph import END, START, StateGraph

from app.agentes.estado import AGENTES, EstadoAgente
from app.agentes.herramientas import para_agente
from app.agentes.nodos import Nodos, SesionMcp
from app.integracion.modelo_lenguaje import ModeloLenguaje


def _despues_de_clasificar(estado: EstadoAgente) -> str:
    return "fuera_de_alcance" if estado["agente"] == "fuera_de_alcance" else "actuar"


def _despues_de_actuar(estado: EstadoAgente) -> str:
    return "ejecutar_herramientas" if estado.get("pendientes") else "redactar"


def construir_grafo(
    modelo: ModeloLenguaje, sesion: SesionMcp, herramientas: Iterable[tipos_mcp.Tool]
) -> Any:
    """`herramientas` es el resultado de `tools/list` de la sesión MCP de la consulta."""
    lista = list(herramientas)
    nodos = Nodos(modelo, sesion, {a: para_agente(a, lista) for a in AGENTES})
    # Las sobrecargas de `add_node` no aceptan métodos async con un TypedDict parcial.
    grafo: Any = StateGraph(EstadoAgente)
    grafo.add_node("clasificar", nodos.clasificar)
    grafo.add_node("actuar", nodos.actuar)
    grafo.add_node("ejecutar_herramientas", nodos.ejecutar_herramientas)
    grafo.add_node("redactar", nodos.redactar)
    grafo.add_node("verificar", nodos.verificar)
    grafo.add_node("fuera_de_alcance", nodos.fuera_de_alcance)
    grafo.add_edge(START, "clasificar")
    grafo.add_conditional_edges("clasificar", _despues_de_clasificar)
    grafo.add_conditional_edges("actuar", _despues_de_actuar)
    grafo.add_edge("ejecutar_herramientas", "actuar")
    grafo.add_edge("redactar", "verificar")
    grafo.add_edge("verificar", END)
    grafo.add_edge("fuera_de_alcance", END)
    return grafo.compile()
