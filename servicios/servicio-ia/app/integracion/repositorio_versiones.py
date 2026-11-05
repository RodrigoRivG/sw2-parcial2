"""Versiones de modelos en Firestore, colección `versiones_modelo` (spec-prediccion.md 2.6).

Trabaja con documentos en camelCase; `modelos/` los convierte en `VersionModelo`.
"""

from collections.abc import Callable
from typing import Any

from google.api_core import exceptions as excepciones_google
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from app.integracion.errores import ErrorInfraestructura
from app.integracion.firestore import TIEMPO_LIMITE

COLECCION = "versiones_modelo"
Documento = dict[str, Any]
Verificacion = Callable[[Documento, Documento | None], Documento]
_ERRORES = (excepciones_google.GoogleAPIError, TimeoutError, OSError)


def id_documento(nombre: str, version: int) -> str:
    return f"{nombre}-{version}"


class RepositorioVersionesFirestore:
    def __init__(self, cliente: firestore.AsyncClient) -> None:
        self._cliente = cliente
        self._coleccion = cliente.collection(COLECCION)

    async def registrar_candidata(self, documento: Documento) -> int:
        """Guarda la versión con `version` = última + 1, en una transacción."""
        nombre = documento["nombre"]
        ultima = (
            self._coleccion.where(filter=FieldFilter("nombre", "==", nombre))
            .order_by("version", direction=firestore.Query.DESCENDING)
            .limit(1)
        )

        @firestore.async_transactional
        async def aplicar(transaccion: firestore.AsyncTransaction) -> int:
            anteriores = [f async for f in await transaccion.get(ultima)]
            version = int(anteriores[0].get("version")) + 1 if anteriores else 1
            referencia = self._coleccion.document(id_documento(nombre, version))
            transaccion.create(referencia, {**documento, "version": version})
            return version

        version: int = await self._ejecutar(aplicar)
        return version

    async def obtener(self, nombre: str, version: int) -> Documento | None:
        try:
            foto = await self._coleccion.document(id_documento(nombre, version)).get(
                retry=None, timeout=TIEMPO_LIMITE
            )
        except _ERRORES as error:
            raise ErrorInfraestructura("firestore", type(error).__name__) from None
        return foto.to_dict() if foto.exists else None

    async def listar(self, nombre: str | None = None) -> list[Documento]:
        consulta: Any = self._coleccion
        if nombre:
            consulta = consulta.where(filter=FieldFilter("nombre", "==", nombre))
        try:
            fotos = await consulta.get(retry=None, timeout=TIEMPO_LIMITE)
        except _ERRORES as error:
            raise ErrorInfraestructura("firestore", type(error).__name__) from None
        documentos = [d for f in fotos if (d := f.to_dict()) is not None]
        return sorted(documentos, key=lambda d: (d["nombre"], -int(d["version"])))

    async def vigente(self, nombre: str) -> Documento | None:
        consulta = (
            self._coleccion.where(filter=FieldFilter("nombre", "==", nombre))
            .where(filter=FieldFilter("estado", "==", "VIGENTE"))
            .limit(1)
        )
        try:
            fotos = await consulta.get(retry=None, timeout=TIEMPO_LIMITE)
        except _ERRORES as error:
            raise ErrorInfraestructura("firestore", type(error).__name__) from None
        return fotos[0].to_dict() if fotos else None

    async def publicar(
        self, nombre: str, version: int, verificar: Verificacion
    ) -> Documento | None:
        """Marca la versión `VIGENTE` y retira la anterior, en una sola transacción.

        `verificar(candidata, vigente)` aplica las reglas de publicación: lanza un error si no
        se puede publicar o devuelve los cambios a guardar en la candidata. Devuelve el
        documento publicado, o `None` si la versión no existe.
        """
        referencia = self._coleccion.document(id_documento(nombre, version))
        vigentes = self._coleccion.where(filter=FieldFilter("nombre", "==", nombre)).where(
            filter=FieldFilter("estado", "==", "VIGENTE")
        )

        @firestore.async_transactional
        async def aplicar(transaccion: firestore.AsyncTransaction) -> Documento | None:
            foto = await referencia.get(transaction=transaccion, retry=None, timeout=TIEMPO_LIMITE)
            candidata = foto.to_dict() if foto.exists else None
            if candidata is None:
                return None
            anteriores = [f async for f in await transaccion.get(vigentes)]
            vigente = anteriores[0].to_dict() if anteriores else None
            cambios = verificar(candidata, vigente)
            for anterior in anteriores:
                transaccion.update(anterior.reference, {"estado": "RETIRADA"})
            transaccion.update(referencia, {**cambios, "estado": "VIGENTE"})
            return {**candidata, **cambios, "estado": "VIGENTE"}

        resultado: Documento | None = await self._ejecutar(aplicar)
        return resultado

    async def _ejecutar(self, aplicar: Any) -> Any:
        try:
            return await aplicar(self._cliente.transaction())
        except ValueError:
            raise ErrorInfraestructura("firestore", "contención de transacciones") from None
        except _ERRORES as error:
            raise ErrorInfraestructura("firestore", type(error).__name__) from None
