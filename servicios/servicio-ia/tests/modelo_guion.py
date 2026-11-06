"""Modelo de lenguaje con guion para los tests (spec-agentes.md 2.4).

Devuelve las respuestas en orden y registra qué se le pidió en cada llamada.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.integracion.modelo_lenguaje import (
    LlamadaHerramienta,
    Mensaje,
    ModeloLenguajeNoDisponible,
    RespuestaModelo,
)


@dataclass
class Pedido:
    mensajes: list[Mensaje]
    herramientas: list[Mapping[str, Any]] | None
    formato: Mapping[str, Any] | None

    @property
    def nombres_herramientas(self) -> list[str]:
        return [h["function"]["name"] for h in self.herramientas or []]


def agente(nombre: str) -> RespuestaModelo:
    return RespuestaModelo(json.dumps({"agente": nombre}))


def herramientas(*llamadas: tuple[str, dict[str, Any]]) -> RespuestaModelo:
    return RespuestaModelo("", [LlamadaHerramienta(n, a) for n, a in llamadas])


def texto(contenido: str) -> RespuestaModelo:
    return RespuestaModelo(contenido)


def plan_en_dos_pasos(plan: dict[str, Any]) -> tuple[RespuestaModelo, RespuestaModelo]:
    """Respuestas del agente de reportes: primero las fuentes y después el plan."""
    fuentes = list(dict.fromkeys(t["fuente"] for t in plan.get("tablas", [])))
    return RespuestaModelo(json.dumps({"fuentes": fuentes})), RespuestaModelo(json.dumps(plan))


class ModeloGuion:
    nombre = "modelo-guion"

    def __init__(
        self, *guion: RespuestaModelo | Exception, disponible: bool = True, repetir: bool = False
    ) -> None:
        self._guion = list(guion)
        self._repetir = repetir
        self.pedidos: list[Pedido] = []
        self.esta_disponible = disponible

    async def chat(
        self,
        mensajes: Sequence[Mensaje],
        herramientas: Sequence[Mapping[str, Any]] | None = None,
        formato: Mapping[str, Any] | None = None,
    ) -> RespuestaModelo:
        self.pedidos.append(
            Pedido(list(mensajes), list(herramientas) if herramientas else None, formato)
        )
        if not self._guion:
            raise AssertionError("El guion se terminó")
        siguiente = (
            self._guion[0] if self._repetir and len(self._guion) == 1 else self._guion.pop(0)
        )
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    async def disponible(self) -> bool:
        return self.esta_disponible

    async def comprobar(self) -> None:
        if not self.esta_disponible:
            raise ModeloLenguajeNoDisponible
