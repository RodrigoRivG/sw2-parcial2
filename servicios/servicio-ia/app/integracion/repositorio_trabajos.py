"""Repositorio de trabajos en MongoDB; transiciones condicionales atómicas."""

from datetime import datetime
from typing import Any, Protocol

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.integracion.errores import ErrorInfraestructura

COLECCION = "trabajos"
Documento = dict[str, Any]


class RepositorioTrabajos(Protocol):
    async def guardar_nuevo(self, documento: Documento) -> None: ...

    async def obtener(self, id_trabajo: str) -> Documento | None: ...

    async def cambiar_estado(
        self, id_trabajo: str, desde: str, hacia: str, cambios: Documento
    ) -> bool: ...

    async def listar_vencidos(
        self, ahora: datetime, creados_antes: datetime, limite: int = 100
    ) -> list[Documento]: ...


def _falla(error: Exception) -> ErrorInfraestructura:
    return ErrorInfraestructura("mongodb", type(error).__name__)


_ERRORES = (PyMongoError, TimeoutError, OSError)


class RepositorioTrabajosMongo:
    def __init__(self, base: AsyncDatabase[Documento]) -> None:
        self._coleccion = base[COLECCION]

    async def guardar_nuevo(self, documento: Documento) -> None:
        try:
            await self._coleccion.insert_one({**documento, "_id": documento["id"]})
        except DuplicateKeyError:
            raise ValueError(f"El trabajo {documento['id']} ya existe") from None
        except _ERRORES as error:
            raise _falla(error) from None

    async def obtener(self, id_trabajo: str) -> Documento | None:
        try:
            return await self._coleccion.find_one({"_id": id_trabajo}, {"_id": 0})
        except _ERRORES as error:
            raise _falla(error) from None

    async def cambiar_estado(
        self, id_trabajo: str, desde: str, hacia: str, cambios: Documento
    ) -> bool:
        try:
            resultado = await self._coleccion.update_one(
                {"_id": id_trabajo, "estado": desde},
                {"$set": {**cambios, "estado": hacia}},
            )
            return resultado.matched_count == 1
        except _ERRORES as error:
            raise _falla(error) from None

    async def listar_vencidos(
        self, ahora: datetime, creados_antes: datetime, limite: int = 100
    ) -> list[Documento]:
        try:
            procesando = self._coleccion.find(
                {"estado": "PROCESANDO", "fechaLimite": {"$lt": ahora}}, {"_id": 0}
            ).limit(limite)
            en_cola = self._coleccion.find(
                {"estado": "EN_COLA", "fechaCreacion": {"$lt": creados_antes}}, {"_id": 0}
            ).limit(limite)
            return [*await procesando.to_list(length=limite), *await en_cola.to_list(length=limite)]
        except _ERRORES as error:
            raise _falla(error) from None
