"""Registro de tipos de trabajo: cada spec registra el suyo (spec-trabajos.md 2.7)."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol

from app.trabajos.esquemas import Trabajo


class Manejador(Protocol):
    """Procesa un trabajo y devuelve su resultado como JSON (sin `Decimal` ni objetos).

    Los errores esperados se lanzan como `ErrorAplicacion`: su código y mensaje van al
    `error` del trabajo.
    """

    async def __call__(self, trabajo: Trabajo) -> dict[str, Any]: ...


@dataclass(frozen=True)
class DefinicionTipo:
    tipo: str
    manejador: Manejador
    tiempo_limite: timedelta


class RegistroTipos:
    def __init__(self) -> None:
        self._definiciones: dict[str, DefinicionTipo] = {}

    def registrar(self, definicion: DefinicionTipo) -> None:
        if definicion.tipo in self._definiciones:
            raise ValueError(f"Tipo de trabajo ya registrado: {definicion.tipo}")
        self._definiciones[definicion.tipo] = definicion

    def obtener(self, tipo: str) -> DefinicionTipo:
        try:
            return self._definiciones[tipo]
        except KeyError:
            raise KeyError(f"Tipo de trabajo no registrado: {tipo}") from None

    def __contains__(self, tipo: object) -> bool:
        return tipo in self._definiciones
