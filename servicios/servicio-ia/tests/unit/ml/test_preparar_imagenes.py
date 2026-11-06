"""Muestra de imágenes con lectura remota de zips (spec-vision.md, Historia 5 y 2.3)."""

import csv
import io
import re
import tarfile
import threading
import zipfile
from collections import Counter
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from PIL import Image

from app.ml.datos import preparar_imagenes as modulo
from app.ml.datos.preparar_imagenes import (
    Fuente,
    Preparador,
    Zip,
    empaquetar,
    escribir_manifiesto,
    particionar,
)


def _foto(color: tuple[int, int, int], tamanio: tuple[int, int] = (600, 400)) -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", tamanio, color).save(salida, format="JPEG", quality=95)
    return salida.getvalue()


def _zip(miembros: dict[str, bytes]) -> bytes:
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_STORED) as archivo:
        for nombre, datos in miembros.items():
            archivo.writestr(nombre, datos)
    return salida.getvalue()


class Servidor:
    """Sirve zips en memoria respondiendo solo a pedidos con `Range` (206)."""

    def __init__(self, archivos: dict[str, bytes]) -> None:
        self.archivos = archivos
        self.bytes_servidos = 0
        servidor = self

        class Manejador(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                datos = servidor.archivos[self.path]
                inicio, fin = (int(x) for x in re.findall(r"\d+", self.headers["Range"]))
                fin = min(fin, len(datos) - 1)
                parte = datos[inicio : fin + 1]
                servidor.bytes_servidos += len(parte)
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {inicio}-{fin}/{len(datos)}")
                self.send_header("Content-Length", str(len(parte)))
                self.end_headers()
                self.wfile.write(parte)

            def log_message(self, *_: object) -> None:
                return

        self._http = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.url = f"http://127.0.0.1:{self._http.server_port}"
        threading.Thread(target=self._http.serve_forever, daemon=True).start()

    def cerrar(self) -> None:
        self._http.shutdown()


@pytest.fixture
def servidor(monkeypatch: pytest.MonkeyPatch) -> Iterator[Servidor]:
    asdid = {f"healthy/healthy_{i}.jpg": _foto((10 * i, 120, 40)) for i in range(8)}
    asdid["healthy/healthy_8.jpg"] = asdid["healthy/healthy_0.jpg"]  # duplicada
    asdid["healthy/danada.jpg"] = b"no es una imagen"
    asdid["healthy/leeme.txt"] = b"se ignora"
    asdid["__MACOSX/healthy/._healthy_1.jpg"] = b"metadatos de macOS"  # se salta sin pedirla
    plantvillage = {
        f"Raiz/Corn___Common_rust/r{i}.JPG": _foto((200, 10 * i, 10), (256, 256)) for i in range(6)
    }
    plantvillage.update({f"Raiz/Corn___healthy/s{i}.jpg": _foto((5, 9 * i, 200)) for i in range(6)})
    plantvillage["Raiz/Tomato___healthy/t0.jpg"] = _foto((1, 1, 1))  # carpeta que no se usa
    archivos = {"/asdid.zip": _zip(asdid), "/pv.zip": _zip(plantvillage)}
    servidor = Servidor(archivos)
    monkeypatch.setattr(
        modulo,
        "FUENTES",
        (
            Fuente(
                "ASDID",
                "prueba",
                "CC0 1.0",
                (Zip(f"{servidor.url}/asdid.zip", "md5:x", 0, {"": "SOYA_SANA"}),),
            ),
            Fuente(
                "PlantVillage",
                "prueba",
                "CC0 1.0",
                (
                    Zip(
                        f"{servidor.url}/pv.zip",
                        "sha256:x",
                        0,
                        {
                            "Raiz/Corn___Common_rust/": "MAIZ_ROYA_COMUN",
                            "Raiz/Corn___healthy/": "MAIZ_SANO",
                        },
                    ),
                ),
            ),
        ),
    )
    yield servidor
    servidor.cerrar()


def _preparar(salida: Path, por_clase: int = 5, semilla: int = 7) -> Preparador:
    preparador = Preparador(por_clase, semilla, salida, esperar=lambda _: None)
    preparador.ejecutar()
    return preparador


def test_descarga_solo_lo_necesario_y_reduce(servidor: Servidor, tmp_path: Path) -> None:
    preparador = _preparar(tmp_path)
    resultado = preparador.resultado

    assert Counter(f["etiqueta"] for f in resultado.filas) == {
        "SOYA_SANA": 5,
        "MAIZ_ROYA_COMUN": 5,
        "MAIZ_SANO": 5,
    }
    assert resultado.bytes_descargados == servidor.bytes_servidos
    assert resultado.bytes_descargados < sum(len(d) for d in servidor.archivos.values())
    assert {f["fuente"] for f in resultado.filas} == {"ASDID", "PlantVillage"}
    for fila in resultado.filas:
        with Image.open(tmp_path / fila["archivo"]) as imagen:
            assert imagen.format == "JPEG"
            assert min(imagen.size) == 256  # 600x400 → 384x256; 256x256 sin agrandar
    assert len({f["sha256"] for f in resultado.filas}) == len(resultado.filas)


def test_reemplaza_danadas_y_duplicadas_cuando_hacen_falta(
    servidor: Servidor, tmp_path: Path
) -> None:
    resultado = _preparar(tmp_path, por_clase=9).resultado  # pide más de las 8 válidas

    soya = [f for f in resultado.filas if f["etiqueta"] == "SOYA_SANA"]
    assert len(soya) == 8  # 10 fotos: 1 dañada y 1 duplicada quedan fuera
    assert not any(f["origen"].endswith(("danada.jpg", ".txt")) for f in soya)
    assert resultado.reemplazadas["SOYA_SANA"] == 2


def test_misma_semilla_mismas_fotos_y_retoma_sin_descargar(
    servidor: Servidor, tmp_path: Path
) -> None:
    primero = _preparar(tmp_path).resultado
    servido_antes = servidor.bytes_servidos
    segundo = _preparar(tmp_path).resultado  # misma carpeta: las fotos ya están

    assert sorted(f["archivo"] for f in primero.filas) == sorted(
        f["archivo"] for f in segundo.filas
    )
    assert segundo.bytes_descargados < primero.bytes_descargados / 2  # solo los índices de los zips
    assert servidor.bytes_servidos - servido_antes == segundo.bytes_descargados


def test_otra_semilla_elige_otras_fotos(servidor: Servidor, tmp_path: Path) -> None:
    a = {f["archivo"] for f in _preparar(tmp_path / "a", semilla=1).resultado.filas}
    b = {f["archivo"] for f in _preparar(tmp_path / "b", semilla=2).resultado.filas}

    assert a != b


def test_particiones_estratificadas_70_15_15() -> None:
    particiones = particionar([f"f{i}" for i in range(50)], semilla=42)

    assert Counter(particiones.values()) == {"entrenamiento": 35, "validacion": 7, "prueba": 8}
    assert particionar([f"f{i}" for i in range(50)], semilla=42) == particiones


def test_manifiesto_y_tar_reproducible(servidor: Servidor, tmp_path: Path) -> None:
    resultado = _preparar(tmp_path / "fotos").resultado
    escribir_manifiesto(resultado.filas, tmp_path / "manifiesto.csv")
    archivos = [f["archivo"] for f in resultado.filas]

    filas = list(csv.DictReader((tmp_path / "manifiesto.csv").open(encoding="utf-8")))
    assert [f["archivo"] for f in filas] == sorted(archivos)
    assert set(filas[0]) == {"archivo", "etiqueta", "fuente", "origen", "particion", "sha256"}
    primero = empaquetar(tmp_path / "fotos", archivos)
    assert primero == empaquetar(tmp_path / "fotos", list(reversed(archivos)))
    with tarfile.open(fileobj=io.BytesIO(primero)) as tar:
        assert sorted(tar.getnames()) == sorted(archivos)


def test_salta_metadatos_de_macos_sin_pedirlos(servidor: Servidor, tmp_path: Path) -> None:
    resultado = _preparar(tmp_path, por_clase=9).resultado

    assert not any("__MACOSX" in f["origen"] for f in resultado.filas)
    assert resultado.reemplazadas["SOYA_SANA"] == 2  # solo la dañada y la duplicada
