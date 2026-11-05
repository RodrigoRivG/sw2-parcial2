"""Repositorio de trabajos asíncronos en Firestore (spec-trabajos.md 2.5).

Las llamadas van sin los reintentos internos del cliente (`retry=None`): con ellos, un
Firestore caído tarda cerca de un minuto en fallar. Los reintentos los hace el consumidor
(1 s, 2 s y 4 s) y la API responde 503 en como máximo `TIEMPO_LIMITE` segundos.

Trabaja con documentos (diccionarios en camelCase); `trabajos/` los convierte en `Trabajo`.
Así `integracion` no depende de ningún módulo de capacidad (constitución §3).
"""

from datetime import datetime
from typing import Any, Protocol

from google.api_core import exceptions as excepciones_google
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from app.integracion.errores import ErrorInfraestructura
from app.integracion.firestore import TIEMPO_LIMITE

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
    return ErrorInfraestructura("firestore", type(error).__name__)


_ERRORES = (excepciones_google.GoogleAPIError, TimeoutError, OSError)


class RepositorioTrabajosFirestore:
    def __init__(self, cliente: firestore.AsyncClient) -> None:
        self._cliente = cliente
        self._coleccion = cliente.collection(COLECCION)

    async def guardar_nuevo(self, documento: Documento) -> None:
        referencia = self._coleccion.document(documento["id"])
        try:
            await referencia.create(documento, retry=None, timeout=TIEMPO_LIMITE)
        except excepciones_google.AlreadyExists:
            raise ValueError(f"El trabajo {documento['id']} ya existe") from None
        except _ERRORES as error:
            raise _falla(error) from None

    async def obtener(self, id_trabajo: str) -> Documento | None:
        try:
            foto = await self._coleccion.document(id_trabajo).get(retry=None, timeout=TIEMPO_LIMITE)
        except _ERRORES as error:
            raise _falla(error) from None
        return foto.to_dict() if foto.exists else None

    async def cambiar_estado(
        self, id_trabajo: str, desde: str, hacia: str, cambios: Documento
    ) -> bool:
        referencia = self._coleccion.document(id_trabajo)

        @firestore.async_transactional
        async def aplicar(transaccion: firestore.AsyncTransaction) -> bool:
            foto = await referencia.get(transaction=transaccion, retry=None, timeout=TIEMPO_LIMITE)
            if not foto.exists or foto.get("estado") != desde:
                return False
            transaccion.update(referencia, {**cambios, "estado": hacia})
            return True

        try:
            resultado: bool = await aplicar(self._cliente.transaction())
        except ValueError:
            # La librería agota sus intentos ante transacciones que chocan: se trata como
            # falla pasajera; el consumidor reintenta y verá el estado ya cambiado.
            raise ErrorInfraestructura("firestore", "contención de transacciones") from None
        except _ERRORES as error:
            raise _falla(error) from None
        return resultado

    async def listar_vencidos(
        self, ahora: datetime, creados_antes: datetime, limite: int = 100
    ) -> list[Documento]:
        en_proceso = (
            self._coleccion.where(filter=FieldFilter("estado", "==", "PROCESANDO"))
            .where(filter=FieldFilter("fechaLimite", "<", ahora))
            .limit(limite)
        )
        en_cola = (
            self._coleccion.where(filter=FieldFilter("estado", "==", "EN_COLA"))
            .where(filter=FieldFilter("fechaCreacion", "<", creados_antes))
            .limit(limite)
        )
        try:
            fotos = [*await en_proceso.get(retry=None, timeout=TIEMPO_LIMITE)]
            fotos += await en_cola.get(retry=None, timeout=TIEMPO_LIMITE)
        except _ERRORES as error:
            raise _falla(error) from None
        return [d for f in fotos if (d := f.to_dict()) is not None]
