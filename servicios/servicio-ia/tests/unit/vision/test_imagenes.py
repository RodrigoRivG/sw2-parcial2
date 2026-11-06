"""vision/imagenes.py (spec-vision.md, Historia 1, escenarios 3 y 4, y casos borde)."""

import io

import numpy as np
import pytest
from PIL import Image

from app.vision.imagenes import ImagenInvalida, preparar_imagen, validar_imagen


def _bytes(imagen: Image.Image, formato: str, **opciones: object) -> bytes:
    salida = io.BytesIO()
    imagen.save(salida, format=formato, **opciones)
    return salida.getvalue()


@pytest.mark.parametrize("formato", ["JPEG", "PNG"])
def test_acepta_jpeg_y_png(formato: str) -> None:
    imagen = validar_imagen(_bytes(Image.new("RGB", (300, 200), "green"), formato))

    assert imagen.size == (300, 200)


@pytest.mark.parametrize(
    "datos",
    [
        b"no es una imagen",
        _bytes(Image.new("RGB", (100, 100)), "GIF"),
        _bytes(Image.new("RGB", (100, 100)), "BMP"),
        _bytes(Image.new("RGB", (63, 200)), "PNG"),
        _bytes(Image.new("RGB", (300, 300)), "JPEG")[:400],  # dañada
    ],
    ids=["texto", "gif", "bmp", "chica", "danada"],
)
def test_rechaza_por_contenido(datos: bytes) -> None:
    with pytest.raises(ImagenInvalida):
        validar_imagen(datos)


def test_rechaza_mas_de_40_megapixeles_sin_decodificarla() -> None:
    enorme = _bytes(Image.new("1", (8000, 6000)), "PNG")  # 48 MP, pocos KB

    with pytest.raises(ImagenInvalida):
        validar_imagen(enorme)


def test_prepara_224_rgb_float_0_255() -> None:
    arreglo = preparar_imagen(Image.new("RGB", (800, 400), (255, 0, 10)))

    assert arreglo.shape == (224, 224, 3)
    assert arreglo.dtype == np.float32
    assert arreglo[100, 100].tolist() == [255.0, 0.0, 10.0]


def test_recorte_central() -> None:
    imagen = Image.new("RGB", (512, 256), "black")
    imagen.paste((255, 255, 255), (0, 0, 128, 256))  # banda blanca a la izquierda, fuera del centro

    arreglo = preparar_imagen(imagen)

    assert arreglo.max() == 0.0


def test_corrige_la_orientacion_exif() -> None:
    imagen = Image.new("RGB", (400, 300), "black")
    imagen.paste((255, 255, 255), (0, 0, 400, 150))  # mitad superior blanca
    exif = Image.Exif()
    exif[0x0112] = 6  # rotar 90° al mostrar
    leida = validar_imagen(_bytes(imagen, "JPEG", exif=exif.tobytes()))

    arreglo = preparar_imagen(leida)

    # Tras rotar 90° en sentido horario, la mitad blanca queda a la derecha
    assert arreglo[112, 200].mean() > 200
    assert arreglo[112, 20].mean() < 50


@pytest.mark.parametrize("modo", ["RGBA", "LA", "L", "P"])
def test_transparencia_y_grises_se_convierten_a_rgb(modo: str) -> None:
    arreglo = preparar_imagen(validar_imagen(_bytes(Image.new(modo, (100, 100)), "PNG")))

    assert arreglo.shape == (224, 224, 3)
