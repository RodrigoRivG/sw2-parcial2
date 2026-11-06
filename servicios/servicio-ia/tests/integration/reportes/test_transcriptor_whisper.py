"""Whisper real (`tiny`, rápido) con los audios grabados por el usuario (spec-reportes.md T05)."""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.integracion.transcriptor import TranscriptorWhisper, validar_audio
from app.reportes.plan import normalizar_texto

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
pytestmark = pytest.mark.lento


@pytest.fixture(scope="module")
def carpeta_modelos() -> Iterator[str]:
    """La caché del contenedor de desarrollo si existe; si no (pipeline), una carpeta temporal."""
    if os.access("/cache", os.W_OK):
        yield "/cache/whisper"
        return
    with tempfile.TemporaryDirectory() as carpeta:
        yield carpeta


@pytest.mark.parametrize(
    ("audio", "palabras"),
    [
        ("costos.ogg", ("reporte", "costos", "campana", "excel")),
        ("campanias.ogg", ("reporte", "campanas", "finalizadas")),
    ],
)
async def test_transcribe_los_audios_grabados(
    carpeta_modelos: str, audio: str, palabras: tuple[str, ...]
) -> None:
    transcriptor = TranscriptorWhisper("tiny", "cpu", "int8", carpeta_modelos)
    transcriptor.iniciar()
    await transcriptor.esperar(300)
    ruta = FIXTURES / audio

    transcripcion = await transcriptor.transcribir(ruta)

    texto = normalizar_texto(transcripcion.texto)
    assert transcripcion.idioma == "es"
    assert all(p in texto for p in palabras), transcripcion.texto
    assert abs(transcripcion.duracion - validar_audio(ruta)) < 0.5
