"""Transcripción de voz con Faster-Whisper (spec-reportes.md 2.4, constitución §1 y §2).

El modelo se carga en un hilo al arrancar, sin bloquear el inicio; mientras carga,
`disponible()` es `False`. Los reportes dependen del `Protocol`; los tests usan uno fijo.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

_logger = logging.getLogger("app.integracion.transcriptor")
DURACION_MAXIMA = 120.0
# Nombres de formato de PyAV (FFmpeg) de WebM, OGG, WAV y MP3
FORMATOS_AUDIO = {"matroska,webm", "webm", "ogg", "wav", "mp3"}


class AudioInvalido(Exception):
    pass


class TranscriptorNoDisponible(Exception):
    pass


@dataclass(frozen=True)
class Transcripcion:
    texto: str
    idioma: str
    duracion: float


class Transcriptor(Protocol):
    def disponible(self) -> bool: ...

    async def esperar(self, tiempo_limite: float) -> None: ...

    async def transcribir(self, ruta: Path) -> Transcripcion: ...


def validar_audio(ruta: Path) -> float:
    """Duración en segundos de un WebM, OGG, WAV o MP3 con audio de hasta 2 minutos."""
    import av

    try:
        with av.open(str(ruta)) as contenedor:
            if contenedor.format.name not in FORMATOS_AUDIO or not contenedor.streams.audio:
                raise AudioInvalido("formato no admitido o sin pista de audio")
            duracion = _duracion(contenedor)
    except AudioInvalido:
        raise
    except Exception as error:  # FFmpeg no pudo abrirlo: no es audio
        raise AudioInvalido(type(error).__name__) from None
    if duracion <= 0 or duracion > DURACION_MAXIMA:
        raise AudioInvalido(f"duración de {duracion:.1f} s")
    return duracion


def _duracion(contenedor: Any) -> float:
    if contenedor.duration:
        return float(contenedor.duration) / 1_000_000
    # MediaRecorder graba WebM sin duración en la cabecera: se toma del último paquete.
    pista = contenedor.streams.audio[0]
    final = 0.0
    for paquete in contenedor.demux(pista):
        if paquete.pts is not None and paquete.time_base is not None:
            final = max(final, float((paquete.pts + (paquete.duration or 0)) * paquete.time_base))
    return final


class EstadoTranscriptor(StrEnum):
    CARGANDO = "CARGANDO"
    CARGADO = "CARGADO"
    ERROR = "ERROR"
    DESACTIVADO = "DESACTIVADO"


class TranscriptorWhisper:
    def __init__(self, modelo: str, dispositivo: str, cuantizacion: str, carpeta: str) -> None:
        self._parametros = (modelo, dispositivo, cuantizacion, carpeta)
        self._modelo: Any = None
        self.estado = EstadoTranscriptor.CARGANDO
        self._listo = asyncio.Event()
        self._tarea: asyncio.Task[None] | None = None

    def iniciar(self, activo: bool = True) -> None:
        if not activo:
            self.estado = EstadoTranscriptor.DESACTIVADO
            self._listo.set()
            return
        self._tarea = asyncio.create_task(self._cargar(), name="carga-whisper")

    async def _cargar(self) -> None:
        modelo, dispositivo, cuantizacion, carpeta = self._parametros
        try:
            self._modelo = await asyncio.to_thread(
                _crear_modelo, modelo, dispositivo, cuantizacion, carpeta
            )
        except Exception as error:
            self.estado = EstadoTranscriptor.ERROR
            _logger.error("No se pudo cargar Whisper", extra={"motivo": repr(error)})
        else:
            self.estado = EstadoTranscriptor.CARGADO
            _logger.info("Whisper cargado", extra={"modelo": modelo})
        finally:
            self._listo.set()

    def disponible(self) -> bool:
        return self.estado is EstadoTranscriptor.CARGADO

    async def esperar(self, tiempo_limite: float) -> None:
        """Espera la carga inicial (primer arranque: se descarga el modelo)."""
        try:
            await asyncio.wait_for(self._listo.wait(), tiempo_limite)
        except TimeoutError:
            raise TranscriptorNoDisponible from None
        if not self.disponible():
            raise TranscriptorNoDisponible

    async def comprobar(self) -> None:
        """Comprobación de salud informativa."""
        if not self.disponible():
            raise RuntimeError(f"whisper: {self.estado}")

    async def transcribir(self, ruta: Path) -> Transcripcion:
        if not self.disponible():
            raise TranscriptorNoDisponible
        return await asyncio.to_thread(self._transcribir, ruta)

    def _transcribir(self, ruta: Path) -> Transcripcion:
        segmentos, informacion = self._modelo.transcribe(str(ruta), language="es", vad_filter=True)
        texto = " ".join(s.text.strip() for s in segmentos).strip()
        return Transcripcion(texto, informacion.language, float(informacion.duration))

    async def detener(self) -> None:
        if self._tarea is not None and not self._tarea.done():
            self._tarea.cancel()


def _crear_modelo(modelo: str, dispositivo: str, cuantizacion: str, carpeta: str) -> Any:
    from faster_whisper import WhisperModel  # carga CTranslate2 solo al usarlo

    return WhisperModel(
        modelo, device=dispositivo, compute_type=cuantizacion, download_root=carpeta
    )
