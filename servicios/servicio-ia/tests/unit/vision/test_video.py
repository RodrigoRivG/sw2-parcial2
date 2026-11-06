"""vision/video.py (spec-vision.md, Historia 3, escenarios 3 y 4)."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.vision.video import InfoVideo, VideoInvalido, extraer_fotogramas, posiciones, validar_video


def crear_video(
    ruta: Path, segundos: float, fps: int = 10, tamanio: tuple[int, int] = (320, 240)
) -> Path:
    """Video MP4 sintético: cada segundo cambia de color (para reconocer los fotogramas)."""
    escritor = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"mp4v"), fps, tamanio)
    for indice in range(round(segundos * fps)):
        segundo = indice // fps
        cuadro = np.full((tamanio[1], tamanio[0], 3), (segundo * 7 % 256, 80, 200), dtype=np.uint8)
        escritor.write(cuadro)
    escritor.release()
    return ruta


def test_video_valido(tmp_path: Path) -> None:
    info = validar_video(crear_video(tmp_path / "v.mp4", 5))

    assert info.fotogramas == 50
    assert info.fps == pytest.approx(10)
    assert info.duracion == pytest.approx(5)


def test_mas_de_60_segundos_es_invalido(tmp_path: Path) -> None:
    with pytest.raises(VideoInvalido):
        validar_video(crear_video(tmp_path / "largo.mp4", 61, fps=2, tamanio=(64, 64)))


@pytest.mark.parametrize("contenido", [b"no es un video", b""])
def test_archivo_que_no_es_video(tmp_path: Path, contenido: bytes) -> None:
    ruta = tmp_path / "falso.mp4"
    ruta.write_bytes(contenido)

    with pytest.raises(VideoInvalido):
        validar_video(ruta)


def test_posiciones_uno_por_segundo_o_30_uniformes() -> None:
    assert posiciones(InfoVideo(fotogramas=50, fps=10)) == [0, 10, 20, 30, 40]
    largas = posiciones(InfoVideo(fotogramas=600, fps=10))  # 60 s
    assert len(largas) == 30
    assert largas[:3] == [0, 20, 40]
    assert all(b - a == 20 for a, b in zip(largas, largas[1:], strict=False))


def test_extrae_fotogramas_preparados_en_orden(tmp_path: Path) -> None:
    ruta = crear_video(tmp_path / "v.mp4", 3)

    fotogramas = extraer_fotogramas(ruta, validar_video(ruta))

    assert [s for s, _ in fotogramas] == [0.0, 1.0, 2.0]
    assert all(f.shape == (224, 224, 3) and f.dtype == np.float32 for _, f in fotogramas)
    assert fotogramas[0][1][112, 112, 2] == pytest.approx(0, abs=8)  # BGR → RGB
