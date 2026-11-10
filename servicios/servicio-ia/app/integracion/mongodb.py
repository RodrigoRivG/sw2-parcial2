"""Cliente MongoDB compartido con fechas UTC y operaciones acotadas."""

from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

TIEMPO_LIMITE = 5.0


def crear_cliente_mongo(uri: str) -> AsyncMongoClient[dict[str, Any]]:
    return AsyncMongoClient(uri, tz_aware=True, timeoutMS=int(TIEMPO_LIMITE * 1000))


async def comprobar_mongo(base: AsyncDatabase[dict[str, Any]]) -> None:
    await base.command("ping")
