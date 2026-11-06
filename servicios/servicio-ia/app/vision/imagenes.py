"""Validación y preparación de imágenes: funciones puras con Pillow (spec-vision.md 2.6).

`preparar_imagen` es el mismo preprocesamiento de validación del entrenamiento y el que se
documenta para los dispositivos: lado menor a 256 px, recorte central de 224 × 224, RGB de 0 a
255 en `float32` (la normalización la hace el modelo).
"""

import io

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps, UnidentifiedImageError

FORMATOS = ("JPEG", "PNG")
LADO_MINIMO = 64
MEGAPIXELES_MAXIMOS = 40_000_000
LADO_REDUCCION = 256
LADO_ENTRADA = 224

# Pillow advierte por encima de este valor y falla por encima del doble; además se valida a mano
Image.MAX_IMAGE_PIXELS = MEGAPIXELES_MAXIMOS


class ImagenInvalida(Exception):
    """El archivo no es una imagen JPEG o PNG utilizable."""


def validar_imagen(datos: bytes) -> Image.Image:
    """Valida por contenido (no por extensión) y devuelve la imagen ya decodificada."""
    try:
        imagen = Image.open(io.BytesIO(datos))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ImagenInvalida(str(error)) from None
    if imagen.format not in FORMATOS:
        raise ImagenInvalida(f"Formato no admitido: {imagen.format}")
    ancho, alto = imagen.size
    if ancho < LADO_MINIMO or alto < LADO_MINIMO:
        raise ImagenInvalida(f"Imagen demasiado pequeña: {ancho}x{alto}")
    if ancho * alto > MEGAPIXELES_MAXIMOS:
        raise ImagenInvalida(f"Imagen demasiado grande: {ancho}x{alto}")
    try:
        imagen.load()
    except Exception as error:  # Pillow lanza distintos errores para archivos dañados
        raise ImagenInvalida(f"Imagen dañada: {error}") from None
    return imagen


def preparar_imagen(imagen: Image.Image) -> NDArray[np.float32]:
    """Orientación EXIF, RGB, lado menor a 256 px, recorte central 224 × 224, `float32` 0-255."""
    imagen = ImageOps.exif_transpose(imagen).convert("RGB")
    ancho, alto = imagen.size
    factor = LADO_REDUCCION / min(ancho, alto)
    imagen = imagen.resize(
        (max(LADO_REDUCCION, round(ancho * factor)), max(LADO_REDUCCION, round(alto * factor))),
        Image.Resampling.BILINEAR,
    )
    ancho, alto = imagen.size
    izquierda = (ancho - LADO_ENTRADA) // 2
    arriba = (alto - LADO_ENTRADA) // 2
    recorte = imagen.crop((izquierda, arriba, izquierda + LADO_ENTRADA, arriba + LADO_ENTRADA))
    return np.asarray(recorte, dtype=np.float32)
