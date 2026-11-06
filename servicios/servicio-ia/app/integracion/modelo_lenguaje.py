"""Modelo de lenguaje local con Ollama (spec-agentes.md 2.4, constitución §1 y §6).

Los agentes dependen del `Protocol`; los tests usan un modelo con guion en su lugar.
"""

import json
import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import ollama

_logger = logging.getLogger("app.integracion.modelo_lenguaje")
TIEMPO_LIMITE_LLAMADA = 60.0
CACHE_DISPONIBLE = 30.0
# Ollama descarga el modelo tras 5 min sin uso y la carga en frío tarda unos 30 s: se mantiene
# cargado durante una sesión de uso.
MANTENER_CARGADO = "30m"

Mensaje = dict[str, Any]


class ModeloLenguajeNoDisponible(Exception):
    pass


@dataclass(frozen=True)
class LlamadaHerramienta:
    nombre: str
    argumentos: dict[str, Any]


@dataclass(frozen=True)
class RespuestaModelo:
    texto: str
    llamadas: list[LlamadaHerramienta] = field(default_factory=list)


class ModeloLenguaje(Protocol):
    nombre: str

    async def chat(
        self,
        mensajes: Sequence[Mensaje],
        herramientas: Sequence[Mapping[str, Any]] | None = None,
        formato: Mapping[str, Any] | None = None,
    ) -> RespuestaModelo: ...

    async def disponible(self) -> bool: ...


class ModeloOllama:
    def __init__(
        self,
        url_base: str,
        modelo: str,
        num_ctx: int = 8192,
        tiempo_limite: float = TIEMPO_LIMITE_LLAMADA,
    ) -> None:
        self.nombre = modelo
        self._num_ctx = num_ctx
        self._cliente = ollama.AsyncClient(host=url_base, timeout=tiempo_limite)
        self._disponible: tuple[float, bool] | None = None

    async def chat(
        self,
        mensajes: Sequence[Mensaje],
        herramientas: Sequence[Mapping[str, Any]] | None = None,
        formato: Mapping[str, Any] | None = None,
    ) -> RespuestaModelo:
        try:
            respuesta = await self._cliente.chat(
                model=self.nombre,
                messages=list(mensajes),
                tools=list(herramientas) if herramientas else None,
                format=dict(formato) if formato else None,
                options={"temperature": 0, "num_ctx": self._num_ctx},
                keep_alive=MANTENER_CARGADO,
            )
        except (ConnectionError, ollama.ResponseError, ollama.RequestError, httpx.HTTPError) as e:
            _logger.warning("Ollama no respondió", extra={"motivo": type(e).__name__})
            self._disponible = (time.monotonic(), False)
            raise ModeloLenguajeNoDisponible from None
        mensaje = respuesta.message
        llamadas = [
            LlamadaHerramienta(llamada.function.name, _argumentos(llamada.function.arguments))
            for llamada in mensaje.tool_calls or []
        ]
        return RespuestaModelo(mensaje.content or "", llamadas)

    async def disponible(self) -> bool:
        """`GET /api/tags` con el modelo configurado; el resultado se guarda 30 s (RQ-AGE-08)."""
        ahora = time.monotonic()
        if self._disponible is not None and ahora - self._disponible[0] < CACHE_DISPONIBLE:
            return self._disponible[1]
        try:
            modelos = await self._cliente.list()
            nombres = {m.model for m in modelos.models}
            estado = self.nombre in nombres or f"{self.nombre}:latest" in nombres
        except (ConnectionError, ollama.ResponseError, ollama.RequestError, httpx.HTTPError):
            estado = False
        self._disponible = (ahora, estado)
        return estado

    async def comprobar(self) -> None:
        """Comprobación de salud informativa (spec-agentes.md 2.8)."""
        if not await self.disponible():
            raise RuntimeError(f"Ollama no disponible o sin el modelo {self.nombre}")


def _argumentos(valor: Any) -> dict[str, Any]:
    if isinstance(valor, Mapping):
        return dict(valor)
    if isinstance(valor, str):  # algunos modelos devuelven los argumentos como texto JSON
        try:
            interpretado = json.loads(valor)
        except ValueError:
            return {}
        return interpretado if isinstance(interpretado, dict) else {}
    return {}
