"""Versiones de modelos en MongoDB con publicación transaccional por modelo."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.integracion.errores import ErrorInfraestructura

COLECCION = "versiones_modelo"
Documento = dict[str, Any]
Verificacion = Callable[[Documento, Documento | None], Documento]
_ERRORES = (PyMongoError, TimeoutError, OSError)


def id_documento(nombre: str, version: int) -> str:
    return f"{nombre}-{version}"


class RepositorioVersionesMongo:
    def __init__(self, base: AsyncDatabase[Documento]) -> None:
        self._base = base
        self._coleccion = base[COLECCION]

    async def registrar_candidata(self, documento: Documento) -> int:
        nombre = documento["nombre"]
        try:
            for _ in range(5):
                ultima = await self._coleccion.find_one(
                    {"nombre": nombre}, {"_id": 0}, sort=[("version", -1)]
                )
                version = int(ultima["version"]) + 1 if ultima else 1
                try:
                    await self._coleccion.insert_one(
                        {**documento, "version": version, "_id": id_documento(nombre, version)}
                    )
                    return version
                except DuplicateKeyError:
                    continue
        except _ERRORES as error:
            raise ErrorInfraestructura("mongodb", type(error).__name__) from None
        raise ErrorInfraestructura("mongodb", "contención")

    async def obtener(self, nombre: str, version: int) -> Documento | None:
        try:
            return await self._coleccion.find_one(
                {"_id": id_documento(nombre, version)}, {"_id": 0}
            )
        except _ERRORES as error:
            raise ErrorInfraestructura("mongodb", type(error).__name__) from None

    async def listar(self, nombre: str | None = None) -> list[Documento]:
        try:
            documentos = await self._coleccion.find(
                {"nombre": nombre} if nombre else {}, {"_id": 0}
            ).to_list()
            return sorted(documentos, key=lambda d: (d["nombre"], -int(d["version"])))
        except _ERRORES as error:
            raise ErrorInfraestructura("mongodb", type(error).__name__) from None

    async def vigente(self, nombre: str) -> Documento | None:
        try:
            return await self._coleccion.find_one(
                {"nombre": nombre, "estado": "VIGENTE"}, {"_id": 0}
            )
        except _ERRORES as error:
            raise ErrorInfraestructura("mongodb", type(error).__name__) from None

    async def publicar(
        self, nombre: str, version: int, verificar: Verificacion
    ) -> Documento | None:
        async def aplicar(sesion: AsyncClientSession) -> Documento | None:
            # Escritura común primero: serializa también la primera publicación concurrente.
            await self._base["publicaciones"].update_one(
                {"_id": nombre},
                {"$set": {"version": version, "fecha": datetime.now(UTC)}},
                upsert=True,
                session=sesion,
            )
            candidata = await self._coleccion.find_one(
                {"_id": id_documento(nombre, version)}, {"_id": 0}, session=sesion
            )
            if candidata is None:
                return None
            vigente = await self._coleccion.find_one(
                {"nombre": nombre, "estado": "VIGENTE"}, {"_id": 0}, session=sesion
            )
            cambios = verificar(candidata, vigente)
            await self._coleccion.update_many(
                {"nombre": nombre, "estado": "VIGENTE"},
                {"$set": {"estado": "RETIRADA"}},
                session=sesion,
            )
            await self._coleccion.update_one(
                {"_id": id_documento(nombre, version)},
                {"$set": {**cambios, "estado": "VIGENTE"}},
                session=sesion,
            )
            return {**candidata, **cambios, "estado": "VIGENTE"}

        try:
            async with self._base.client.start_session() as sesion:
                return await sesion.with_transaction(aplicar)
        except _ERRORES as error:
            raise ErrorInfraestructura("mongodb", type(error).__name__) from None
