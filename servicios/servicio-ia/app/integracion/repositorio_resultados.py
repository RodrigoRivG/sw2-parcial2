"""Resultados de modelos en MongoDB, conservando documentos camelCase."""

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from app.integracion.errores import ErrorInfraestructura

Documento = dict[str, Any]
_ERRORES = (PyMongoError, TimeoutError, OSError)


class RepositorioResultadosMongo:
    def __init__(self, base: AsyncDatabase[Documento]) -> None:
        self._base = base

    async def guardar(self, coleccion: str, documento: Documento) -> None:
        try:
            await self._base[coleccion].insert_one({**documento, "_id": documento["id"]})
        except _ERRORES as error:
            raise ErrorInfraestructura("mongodb", type(error).__name__) from None

    async def obtener(self, coleccion: str, id_documento: str) -> Documento | None:
        try:
            return await self._base[coleccion].find_one({"_id": id_documento}, {"_id": 0})
        except _ERRORES as error:
            raise ErrorInfraestructura("mongodb", type(error).__name__) from None

    async def listar(
        self,
        coleccion: str,
        pagina: int,
        tamanio: int,
        igual_a: tuple[str, Any] | None = None,
    ) -> tuple[list[Documento], int]:
        filtro = {igual_a[0]: igual_a[1]} if igual_a is not None else {}
        try:
            total = await self._base[coleccion].count_documents(filtro)
            consulta = self._base[coleccion].find(filtro, {"_id": 0})
            documentos = (
                await consulta.sort("fecha", -1)
                .skip(pagina * tamanio)
                .limit(tamanio)
                .to_list(length=tamanio)
            )
            return documentos, total
        except _ERRORES as error:
            raise ErrorInfraestructura("mongodb", type(error).__name__) from None
