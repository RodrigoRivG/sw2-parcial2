"""Estado del grafo de agentes y sus límites (spec-agentes.md 1.3 RQ-AGE-04 y 2.5)."""

from typing import Any, Literal, TypedDict

from app.integracion.modelo_lenguaje import LlamadaHerramienta, Mensaje

Agente = Literal["campanias", "inventario", "fuera_de_alcance"]
AGENTES: tuple[Agente, ...] = ("campanias", "inventario", "fuera_de_alcance")

MAXIMO_LLAMADAS = 6
# Pasos del grafo: clasificar + 6 rondas de (actuar, ejecutar_herramientas) + el último actuar +
# redactar + verificar. Con 12 (el valor de la spec), un modelo que pide una herramienta por
# turno no llegaría nunca a las 6 llamadas.
MAXIMO_PASOS = 1 + 2 * MAXIMO_LLAMADAS + 3
TIEMPO_LIMITE_CONSULTA = 120.0


class Llamada(TypedDict):
    nombre: str
    argumentos: dict[str, Any]
    resultado: Any
    duracionMs: int
    error: str | None


class EstadoAgente(TypedDict, total=False):
    pregunta: str
    agente: Agente
    mensajes: list[Mensaje]
    pendientes: list[LlamadaHerramienta]
    llamadas: list[Llamada]
    respuesta: str
    cifrasOmitidas: int
