"""Muestra de imágenes de ASDID (soya) y PlantVillage (maíz) para el clasificador.

spec-vision.md 2.3. Descarga solo las fotos elegidas dentro de cada zip remoto, con pedidos de
rangos de bytes, y guarda cada una reducida a 256 px por el lado menor. El original no toca el
disco.

Uso (dentro del contenedor, desde la raíz del servicio):

    python -m app.ml.datos.preparar_imagenes --por-clase 50 [--semilla 42]
        [--salida /cache/imagenes] [--sin-subir]

Escribe `datos/imagenes/manifiesto.csv` y `datos/imagenes/fuentes.json`, y sube el conjunto
empaquetado a `s3://<bucket>/ia/datasets/imagenes/<sha256>.tar`.
"""

import argparse
import asyncio
import csv
import hashlib
import io
import json
import logging
import random
import re
import struct
import sys
import tarfile
import threading
import time
import zipfile
import zlib
from collections import Counter, defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

RAIZ_SERVICIO = Path(__file__).resolve().parents[3]
CARPETA_DATOS = RAIZ_SERVICIO / "datos" / "imagenes"
EXTENSIONES = (".jpg", ".jpeg", ".png")
LADO_MENOR = 256
CALIDAD_JPEG = 90
TAMANIO_BLOQUE = 256 * 1024  # para leer el índice (directorio central) del zip
DESCARGAS_EN_PARALELO = 4
REINTENTOS = (1.0, 2.0, 4.0)
AGENTE = {"User-Agent": "servicio-ia"}

_logger = logging.getLogger("app.ml.preparar_imagenes")


@dataclass(frozen=True)
class Zip:
    url: str
    suma_publicada: str  # "md5:..." o "sha256:..."
    tamanio: int
    etiquetas_por_carpeta: dict[str, str]  # prefijo de carpeta ("" = todo el zip) -> etiqueta


@dataclass(frozen=True)
class Fuente:
    nombre: str
    referencia: str
    licencia: str
    zips: tuple[Zip, ...]


_ZENODO = "https://zenodo.org/records/7304859/files/{}.zip?download=1"
_PV = "Plant_leave_diseases_dataset_without_augmentation"


def _asdid(nombre: str, md5: str, tamanio: int, etiqueta: str) -> Zip:
    return Zip(_ZENODO.format(nombre), f"md5:{md5}", tamanio, {"": etiqueta})


FUENTES = (
    Fuente(
        nombre="ASDID",
        referencia="Auburn Soybean Disease Image Dataset, DOI 10.5061/dryad.41ns1rnj3 "
        "(Zenodo 7304859)",
        licencia="CC0 1.0",
        zips=(
            _asdid(
                "bacterial_blight",
                "31cd576c7b4681eb77942b7fbae59308",
                2847639377,
                "SOYA_TIZON_BACTERIANO",
            ),
            _asdid(
                "cercospora_leaf_blight",
                "0e62c4d31beea7f62f091045f224487c",
                7091853681,
                "SOYA_TIZON_CERCOSPORA",
            ),
            _asdid("downey_mildew", "c13cbb0771be3edc25d4f1a144bb7f5f", 2929109463, "SOYA_MILDIU"),
            _asdid(
                "frogeye", "4dd9b491bdb90f471c0358f4843dee79", 5898670550, "SOYA_MANCHA_OJO_RANA"
            ),
            _asdid("healthy", "0c3e217c230bbcb4f011d9586a40061f", 7104782104, "SOYA_SANA"),
            _asdid(
                "potassium_deficiency",
                "a753aa36070fcdf2f86ef9673d3c6036",
                3393324790,
                "SOYA_DEFICIENCIA_POTASIO",
            ),
            _asdid("soybean_rust", "7eb6e827efe25deeeabe0a33d1d069a9", 8375658860, "SOYA_ROYA"),
            _asdid(
                "target_spot", "5cb8799f4ecfc437439afbf39886e87d", 4254380310, "SOYA_MANCHA_DIANA"
            ),
        ),
    ),
    Fuente(
        nombre="PlantVillage",
        referencia="Data for: Identification of Plant Leaf Diseases Using a 9-layer Deep CNN, "
        "Mendeley Data tywbtsjrjv v1 (imágenes de PlantVillage sin aumento)",
        licencia="CC0 1.0",
        zips=(
            Zip(
                "https://data.mendeley.com/public-files/datasets/tywbtsjrjv/files/"
                "d5652a28-c1d8-4b76-97f3-72fb80f94efc/file_downloaded",
                "sha256:ac3432453984",  # prefijo del SHA-256 publicado por Mendeley
                868032562,
                {
                    "Plant_leave_diseases_dataset_without_augmentation/"
                    "Corn___Cercospora_leaf_spot Gray_leaf_spot/": "MAIZ_MANCHA_GRIS",
                    f"{_PV}/Corn___Common_rust/": "MAIZ_ROYA_COMUN",
                    f"{_PV}/Corn___healthy/": "MAIZ_SANO",
                    "Plant_leave_diseases_dataset_without_augmentation/"
                    "Corn___Northern_Leaf_Blight/": "MAIZ_TIZON_NORTENO",
                },
            ),
        ),
    ),
)


# --- lectura remota de zips --------------------------------------------------------------


class ArchivoHttp(io.RawIOBase):
    """Archivo de solo lectura sobre HTTP con pedidos `Range`.

    `zipfile` solo lo usa para leer el índice del zip, de a pocos KB: un búfer de 256 KB evita
    un pedido por lectura. El contenido de cada foto se pide con `leer_rango`, en un solo pedido
    del tamaño exacto (ver `leer_miembro`).
    """

    def __init__(self, url: str, cliente: httpx.Client, contador: Callable[[int], None]) -> None:
        super().__init__()
        self._cliente = cliente
        self._contador = contador
        respuesta = self._pedir(url, 0, 0)
        self.url = str(respuesta.url)  # después de redirecciones
        self.tamanio = int(respuesta.headers["Content-Range"].rsplit("/", 1)[1])
        self._posicion = 0
        self._bufer_inicio = 0
        self._bufer = b""

    def _pedir(self, url: str, inicio: int, fin: int) -> httpx.Response:
        respuesta = self._cliente.get(url, headers={**AGENTE, "Range": f"bytes={inicio}-{fin}"})
        if respuesta.status_code != 206:
            raise OSError(f"Se esperaba 206 y llegó {respuesta.status_code} de {url}")
        self._contador(len(respuesta.content))
        return respuesta

    def leer_rango(self, inicio: int, cantidad: int) -> bytes:
        return self._pedir(self.url, inicio, inicio + cantidad - 1).content

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._posicion

    def seek(self, desplazamiento: int, desde: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._posicion, io.SEEK_END: self.tamanio}[desde]
        self._posicion = base + desplazamiento
        return self._posicion

    def read(self, cantidad: int = -1) -> bytes:
        if cantidad < 0:
            cantidad = self.tamanio - self._posicion
        if cantidad == 0 or self._posicion >= self.tamanio:
            return b""
        fin = min(self._posicion + cantidad, self.tamanio)
        bufer_fin = self._bufer_inicio + len(self._bufer)
        if not (self._bufer_inicio <= self._posicion and fin <= bufer_fin):
            hasta = min(self.tamanio, self._posicion + max(cantidad, TAMANIO_BLOQUE)) - 1
            self._bufer = self._pedir(self.url, self._posicion, hasta).content
            self._bufer_inicio = self._posicion
        inicio = self._posicion - self._bufer_inicio
        datos = self._bufer[inicio : inicio + (fin - self._posicion)]
        self._posicion += len(datos)
        return datos


_CABECERA_LOCAL = struct.Struct("<4s2B4HL2L2H")  # cabecera local de un miembro de zip (30 bytes)


def leer_miembro(remoto: ArchivoHttp, info: zipfile.ZipInfo) -> bytes:
    """Bytes de un miembro: cabecera local (30 bytes) y datos en un solo pedido exacto."""
    cabecera = _CABECERA_LOCAL.unpack(remoto.leer_rango(info.header_offset, _CABECERA_LOCAL.size))
    if cabecera[0] != b"PK\x03\x04":
        raise zipfile.BadZipFile(f"Cabecera local inválida en {info.filename}")
    largo_nombre, largo_extra = cabecera[-2], cabecera[-1]
    inicio = info.header_offset + _CABECERA_LOCAL.size + largo_nombre + largo_extra
    datos = remoto.leer_rango(inicio, info.compress_size) if info.compress_size else b""
    if info.compress_type == zipfile.ZIP_STORED:
        return datos
    if info.compress_type == zipfile.ZIP_DEFLATED:
        return zlib.decompress(datos, -zlib.MAX_WBITS)
    raise zipfile.BadZipFile(f"Compresión no admitida ({info.compress_type}) en {info.filename}")


# --- selección, reducción y particiones ---------------------------------------------------


@dataclass(frozen=True)
class Candidata:
    fuente: str
    url: str
    info: zipfile.ZipInfo
    etiqueta: str

    @property
    def miembro(self) -> str:
        return self.info.filename


def es_metadato_macos(miembro: str) -> bool:
    """Entradas que macOS agrega al comprimir (`__MACOSX/…/._foto.jpg`): no son imágenes."""
    return miembro.startswith("__MACOSX/") or miembro.rsplit("/", 1)[-1].startswith("._")


def nombre_salida(candidata: Candidata) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]", "_", candidata.miembro.rsplit("/", 1)[-1].rsplit(".", 1)[0])
    return f"{candidata.etiqueta}/{candidata.fuente}_{base}.jpg"


def reducir(datos: bytes) -> bytes:
    """Orientación EXIF, RGB, lado menor de 256 px (sin agrandar) y JPEG de calidad 90."""
    with Image.open(io.BytesIO(datos)) as original:
        imagen: Image.Image = ImageOps.exif_transpose(original).convert("RGB")
        ancho, alto = imagen.size
        factor = LADO_MENOR / min(ancho, alto)
        if factor < 1:
            imagen = imagen.resize(
                (round(ancho * factor), round(alto * factor)), Image.Resampling.LANCZOS
            )
        salida = io.BytesIO()
        imagen.save(salida, format="JPEG", quality=CALIDAD_JPEG)
        return salida.getvalue()


def particionar(nombres: list[str], semilla: int) -> dict[str, str]:
    """70/15/15 estable: entrenamiento, validación y prueba."""
    ordenados = sorted(nombres)
    random.Random(semilla).shuffle(ordenados)
    n = len(ordenados)
    n_entrenamiento = round(n * 0.70)
    n_validacion = int(n * 0.15)
    return {
        nombre: (
            "entrenamiento"
            if i < n_entrenamiento
            else "validacion"
            if i < n_entrenamiento + n_validacion
            else "prueba"
        )
        for i, nombre in enumerate(ordenados)
    }


@dataclass
class Resultado:
    filas: list[dict[str, str]] = field(default_factory=list)
    bytes_descargados: int = 0
    reemplazadas: Counter[str] = field(default_factory=Counter)


class Preparador:
    def __init__(
        self,
        por_clase: int,
        semilla: int,
        salida: Path,
        crear_cliente: Callable[[], httpx.Client] = lambda: httpx.Client(
            follow_redirects=True, timeout=60
        ),
        esperar: Callable[[float], None] = time.sleep,
    ) -> None:
        self.por_clase = por_clase
        self.semilla = semilla
        self.salida = salida
        self._crear_cliente = crear_cliente
        self._esperar = esperar
        self._candado = threading.Lock()
        self._local = threading.local()
        self.resultado = Resultado()

    def _contar(self, bytes_leidos: int) -> None:
        with self._candado:
            self.resultado.bytes_descargados += bytes_leidos

    def _remoto(self, url: str) -> ArchivoHttp:
        """Un archivo remoto por hilo y por URL (los clientes HTTP no se comparten entre hilos)."""
        abiertos: dict[str, ArchivoHttp] = getattr(self._local, "remotos", {})
        self._local.remotos = abiertos
        if url not in abiertos:
            cliente = getattr(self._local, "cliente", None) or self._crear_cliente()
            self._local.cliente = cliente
            abiertos[url] = ArchivoHttp(url, cliente, self._contar)
        return abiertos[url]

    def candidatas(self) -> dict[str, list[Candidata]]:
        """Todas las fotos de cada etiqueta, mezcladas con la semilla (orden de preferencia)."""
        por_etiqueta: dict[str, list[Candidata]] = defaultdict(list)
        for fuente in FUENTES:
            for archivo in fuente.zips:
                for info in zipfile.ZipFile(self._remoto(archivo.url)).infolist():
                    if info.is_dir() or not info.filename.lower().endswith(EXTENSIONES):
                        continue
                    for prefijo, etiqueta in archivo.etiquetas_por_carpeta.items():
                        if info.filename.startswith(prefijo):
                            por_etiqueta[etiqueta].append(
                                Candidata(fuente.nombre, archivo.url, info, etiqueta)
                            )
        for etiqueta, lista in por_etiqueta.items():
            lista.sort(key=lambda c: c.miembro)  # orden estable antes de mezclar
            random.Random(f"{self.semilla}-{etiqueta}").shuffle(lista)
        return dict(por_etiqueta)

    def _obtener(self, candidata: Candidata) -> bytes | None:
        """Foto reducida (desde el disco si ya estaba), o `None` si no se pudo obtener."""
        destino = self.salida / nombre_salida(candidata)
        if destino.exists():
            return destino.read_bytes()
        for intento, espera in enumerate((*REINTENTOS, None)):
            try:
                datos = reducir(leer_miembro(self._remoto(candidata.url), candidata.info))
            except (UnidentifiedImageError, zipfile.BadZipFile, zlib.error) as error:
                # El contenido no es una imagen válida: reintentar no cambia nada
                _logger.warning(
                    "Foto descartada", extra={"miembro": candidata.miembro, "motivo": repr(error)}
                )
                return None
            except (OSError, httpx.HTTPError) as error:
                if espera is None:
                    _logger.warning(
                        "Foto descartada",
                        extra={"miembro": candidata.miembro, "motivo": repr(error)},
                    )
                    return None
                _logger.info("Reintento de descarga", extra={"intento": intento + 1})
                self._esperar(espera)
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(datos)
            return datos
        return None

    def _elegir(self, etiqueta: str, lista: list[Candidata]) -> list[tuple[Candidata, str]]:
        # Las entradas de metadatos de macOS se saltan después de mezclar, sin intentarlas: así
        # las fotos válidas se recorren en el mismo orden con la misma semilla.
        lista = [c for c in lista if not es_metadato_macos(c.miembro)]
        elegidas: list[tuple[Candidata, str]] = []
        vistas: set[str] = set()
        indice = 0
        with ThreadPoolExecutor(DESCARGAS_EN_PARALELO) as hilos:
            while len(elegidas) < self.por_clase and indice < len(lista):
                faltan = self.por_clase - len(elegidas)
                lote = lista[indice : indice + faltan]
                indice += len(lote)
                for candidata, datos in zip(lote, hilos.map(self._obtener, lote), strict=True):
                    huella = hashlib.sha256(datos).hexdigest() if datos else None
                    if huella is None or huella in vistas:
                        self.resultado.reemplazadas[etiqueta] += 1
                        if datos is not None:  # duplicada: se borra del disco
                            (self.salida / nombre_salida(candidata)).unlink(missing_ok=True)
                        continue
                    vistas.add(huella)
                    elegidas.append((candidata, huella))
        return elegidas

    def ejecutar(self) -> Resultado:
        for etiqueta, lista in sorted(self.candidatas().items()):
            elegidas = self._elegir(etiqueta, lista)
            particiones = particionar([nombre_salida(c) for c, _ in elegidas], self.semilla)
            for candidata, huella in elegidas:
                archivo = nombre_salida(candidata)
                self.resultado.filas.append(
                    {
                        "archivo": archivo,
                        "etiqueta": etiqueta,
                        "fuente": candidata.fuente,
                        "origen": candidata.miembro,
                        "particion": particiones[archivo],
                        "sha256": huella,
                    }
                )
            print(f"{etiqueta}: {len(elegidas)} fotos", flush=True)
        return self.resultado


# --- salidas -----------------------------------------------------------------------------

COLUMNAS_MANIFIESTO = ["archivo", "etiqueta", "fuente", "origen", "particion", "sha256"]


def escribir_manifiesto(filas: list[dict[str, str]], ruta: Path) -> None:
    salida = io.StringIO()
    escritor = csv.DictWriter(salida, fieldnames=COLUMNAS_MANIFIESTO, lineterminator="\n")
    escritor.writeheader()
    escritor.writerows(sorted(filas, key=lambda f: f["archivo"]))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(salida.getvalue(), encoding="utf-8")


def empaquetar(carpeta: Path, archivos: list[str]) -> bytes:
    """`.tar` reproducible: mismo contenido, mismos bytes (orden y metadatos fijos)."""
    salida = io.BytesIO()
    with tarfile.open(fileobj=salida, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for nombre in sorted(archivos):
            datos = (carpeta / nombre).read_bytes()
            info = tarfile.TarInfo(nombre)
            info.size = len(datos)
            info.mtime = 0
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(datos))
    return salida.getvalue()


def escribir_fuentes(
    resultado: Resultado, por_clase: int, semilla: int, tar_sha256: str | None, ruta: Path
) -> None:
    datos: dict[str, Any] = {
        "fechaPreparacion": datetime.now(UTC).date().isoformat(),
        "porClase": por_clase,
        "semilla": semilla,
        "bytesDescargadosEnEstaEjecucion": resultado.bytes_descargados,
        "reemplazadas": dict(resultado.reemplazadas),
        "fotosPorEtiqueta": dict(Counter(f["etiqueta"] for f in resultado.filas)),
        "fotosPorParticion": dict(Counter(f["particion"] for f in resultado.filas)),
        "conjunto": {"archivo": f"datasets/imagenes/{tar_sha256}.tar", "sha256": tar_sha256}
        if tar_sha256
        else None,
        "fuentes": [
            {
                "nombre": f.nombre,
                "referencia": f.referencia,
                "licencia": f.licencia,
                "zips": [
                    {"url": z.url, "suma": z.suma_publicada, "tamanio": z.tamanio} for z in f.zips
                ],
            }
            for f in FUENTES
        ],
    }
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def subir_conjunto(contenido: bytes) -> str:
    from app.config import cargar_configuracion
    from app.integracion.almacen_archivos import AlmacenS3

    config = cargar_configuracion()
    almacen = AlmacenS3(config.aws_bucket, config.s3_prefijo, config.aws_endpoint)
    huella = hashlib.sha256(contenido).hexdigest()
    ruta = f"datasets/imagenes/{huella}.tar"
    if await almacen.descargar(ruta) is None:
        await almacen.subir(ruta, contenido, "application/x-tar")
    return huella


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--por-clase", type=int, default=50)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--salida", type=Path, default=Path("/cache/imagenes"))
    parser.add_argument("--sin-subir", action="store_true", help="No sube el .tar a S3")
    opciones = parser.parse_args(argumentos)
    logging.basicConfig(level=logging.WARNING)

    preparador = Preparador(opciones.por_clase, opciones.semilla, opciones.salida)
    resultado = preparador.ejecutar()
    escribir_manifiesto(resultado.filas, CARPETA_DATOS / "manifiesto.csv")
    huella = None
    if not opciones.sin_subir:
        contenido = empaquetar(opciones.salida, [f["archivo"] for f in resultado.filas])
        huella = asyncio.run(subir_conjunto(contenido))
        print(f"Conjunto subido: datasets/imagenes/{huella}.tar ({len(contenido) // 1024} KB)")
    escribir_fuentes(
        resultado, opciones.por_clase, opciones.semilla, huella, CARPETA_DATOS / "fuentes.json"
    )
    print(
        f"Descargados: {resultado.bytes_descargados / 1e6:.1f} MB; "
        f"reemplazadas: {dict(resultado.reemplazadas)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
