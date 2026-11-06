"""Validación de video y extracción de fotogramas con OpenCV (spec-vision.md 2.6, RF-22)."""

import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

from app.vision.imagenes import preparar_imagen

DURACION_MAXIMA_SEGUNDOS = 60.0
MAXIMO_FOTOGRAMAS = 30


class VideoInvalido(Exception):
    """No se puede decodificar como video o dura más de 60 s."""


@dataclass(frozen=True)
class InfoVideo:
    fotogramas: int
    fps: float

    @property
    def duracion(self) -> float:
        return self.fotogramas / self.fps


def validar_video(ruta: Path) -> InfoVideo:
    captura = cv2.VideoCapture(str(ruta))
    try:
        if not captura.isOpened():
            raise VideoInvalido("No se pudo abrir como video")
        fotogramas = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(captura.get(cv2.CAP_PROP_FPS))
        leido, _ = captura.read()
    finally:
        captura.release()
    if not leido or fotogramas <= 0 or fps <= 0:
        raise VideoInvalido("El video no tiene fotogramas legibles")
    info = InfoVideo(fotogramas, fps)
    if info.duracion > DURACION_MAXIMA_SEGUNDOS:
        raise VideoInvalido(f"Dura {info.duracion:.1f} s")
    return info


def posiciones(info: InfoVideo, maximo: int = MAXIMO_FOTOGRAMAS) -> list[int]:
    """Uno por segundo si dura `maximo` segundos o menos; si no, `maximo` uniformes."""
    if info.duracion <= maximo:
        cantidad = max(1, math.ceil(info.duracion))
        return [min(info.fotogramas - 1, round(i * info.fps)) for i in range(cantidad)]
    return [round(i * info.fotogramas / maximo) for i in range(maximo)]


def extraer_fotogramas(
    ruta: Path, info: InfoVideo, maximo: int = MAXIMO_FOTOGRAMAS
) -> list[tuple[float, NDArray[np.float32]]]:
    """(segundo, imagen preparada) de cada fotograma elegido, en orden."""
    captura = cv2.VideoCapture(str(ruta))
    resultado: list[tuple[float, NDArray[np.float32]]] = []
    try:
        for posicion in posiciones(info, maximo):
            captura.set(cv2.CAP_PROP_POS_FRAMES, posicion)
            leido, cuadro = captura.read()
            if not leido:
                continue
            imagen = Image.fromarray(cv2.cvtColor(cuadro, cv2.COLOR_BGR2RGB))
            resultado.append((posicion / info.fps, preparar_imagen(imagen)))
    finally:
        captura.release()
    if not resultado:
        raise VideoInvalido("No se pudo leer ningún fotograma")
    return resultado
