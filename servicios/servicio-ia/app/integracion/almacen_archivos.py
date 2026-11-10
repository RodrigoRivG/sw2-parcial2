"""Archivos privados en S3; las rutas lógicas se aíslan bajo un prefijo."""

import asyncio
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.integracion.errores import ErrorInfraestructura

TIEMPO_LIMITE = 60.0
_ERRORES = (BotoCoreError, ClientError, TimeoutError, OSError)


class AlmacenArchivos(Protocol):
    async def subir(self, ruta: str, datos: bytes, tipo_contenido: str) -> None: ...

    async def descargar(self, ruta: str) -> bytes | None:
        """Contenido del archivo, o `None` si no existe."""
        ...

    async def borrar(self, ruta: str) -> None:
        """Borra el archivo; no falla si ya no existe."""
        ...


class AlmacenS3:
    def __init__(self, bucket: str, prefijo: str = "ia/", endpoint: str | None = None) -> None:
        self._bucket = bucket
        self._prefijo = prefijo.strip("/") + "/" if prefijo.strip("/") else ""
        self._cliente = boto3.client(
            "s3",
            endpoint_url=endpoint or None,
            config=Config(
                retries={"total_max_attempts": 1},
                connect_timeout=5,
                read_timeout=60,
                s3={"addressing_style": "path" if endpoint else "auto"},
            ),
        )

    async def subir(self, ruta: str, datos: bytes, tipo_contenido: str) -> None:
        try:
            await asyncio.to_thread(
                self._cliente.put_object,
                Bucket=self._bucket,
                Key=self._prefijo + ruta,
                Body=datos,
                ContentType=tipo_contenido,
            )
        except _ERRORES as error:
            raise ErrorInfraestructura("s3", type(error).__name__) from None

    def _descargar(self, ruta: str) -> bytes:
        respuesta = self._cliente.get_object(Bucket=self._bucket, Key=self._prefijo + ruta)
        with respuesta["Body"] as contenido:
            datos: bytes = contenido.read()
        return datos

    async def descargar(self, ruta: str) -> bytes | None:
        try:
            return await asyncio.to_thread(self._descargar, ruta)
        except ClientError as error:
            if error.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise ErrorInfraestructura("s3", type(error).__name__) from None
        except _ERRORES as error:
            raise ErrorInfraestructura("s3", type(error).__name__) from None

    async def borrar(self, ruta: str) -> None:
        try:
            await asyncio.to_thread(
                self._cliente.delete_object, Bucket=self._bucket, Key=self._prefijo + ruta
            )
        except _ERRORES as error:
            raise ErrorInfraestructura("s3", type(error).__name__) from None
