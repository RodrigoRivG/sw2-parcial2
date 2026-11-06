"""Almacén de archivos en Cloud Storage (usa el emulador si existe STORAGE_EMULATOR_HOST).

El cliente de Cloud Storage es síncrono: cada operación corre en un hilo. Las llamadas van sin
los reintentos internos de la librería (`retry=None`), que con un servicio caído esperan hasta
120 s; los reintentos los decide quien llama.
"""

import asyncio
from typing import Protocol

from google.api_core import exceptions as excepciones_google
from google.cloud import storage  # type: ignore[attr-defined]
from requests import exceptions as excepciones_http

from app.integracion.errores import ErrorInfraestructura

TIEMPO_LIMITE = 60.0
_ERRORES = (excepciones_google.GoogleAPIError, excepciones_http.RequestException, OSError)


class AlmacenArchivos(Protocol):
    async def subir(self, ruta: str, datos: bytes, tipo_contenido: str) -> None: ...

    async def descargar(self, ruta: str) -> bytes | None:
        """Contenido del archivo, o `None` si no existe."""
        ...

    async def borrar(self, ruta: str) -> None:
        """Borra el archivo; no falla si ya no existe."""
        ...


class AlmacenGcs:
    def __init__(self, proyecto: str, nombre_bucket: str) -> None:
        self._bucket = storage.Client(project=proyecto).bucket(nombre_bucket)

    async def subir(self, ruta: str, datos: bytes, tipo_contenido: str) -> None:
        blob = self._bucket.blob(ruta)
        try:
            await asyncio.to_thread(
                blob.upload_from_string,
                datos,
                content_type=tipo_contenido,
                timeout=TIEMPO_LIMITE,
                retry=None,
            )
        except _ERRORES as error:
            raise ErrorInfraestructura("gcs", type(error).__name__) from None

    async def descargar(self, ruta: str) -> bytes | None:
        blob = self._bucket.blob(ruta)
        try:
            datos: bytes = await asyncio.to_thread(
                blob.download_as_bytes, timeout=TIEMPO_LIMITE, retry=None
            )
        except excepciones_google.NotFound:
            return None
        except _ERRORES as error:
            raise ErrorInfraestructura("gcs", type(error).__name__) from None
        return datos

    async def borrar(self, ruta: str) -> None:
        blob = self._bucket.blob(ruta)
        try:
            await asyncio.to_thread(blob.delete, timeout=TIEMPO_LIMITE, retry=None)
        except excepciones_google.NotFound:
            return
        except _ERRORES as error:
            raise ErrorInfraestructura("gcs", type(error).__name__) from None
