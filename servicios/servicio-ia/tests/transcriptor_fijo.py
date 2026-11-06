"""Transcriptor de prueba: devuelve un texto dado (spec-reportes.md 2.4)."""

import asyncio
from pathlib import Path

from app.integracion.transcriptor import Transcripcion, TranscriptorNoDisponible


class TranscriptorFijo:
    def __init__(self, texto: str = "", disponible: bool = True) -> None:
        self.texto = texto
        self.esta_disponible = disponible
        self.recibidos: list[bytes] = []

    def disponible(self) -> bool:
        return self.esta_disponible

    async def esperar(self, tiempo_limite: float) -> None:
        if not self.esta_disponible:
            raise TranscriptorNoDisponible

    async def transcribir(self, ruta: Path) -> Transcripcion:
        self.recibidos.append(await asyncio.to_thread(ruta.read_bytes))
        return Transcripcion(self.texto, "es", 3.0)
