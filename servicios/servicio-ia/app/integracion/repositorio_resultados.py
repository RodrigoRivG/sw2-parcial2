"""Resultados de los modelos en Firestore: colecciones `predicciones` y `analisis`.

Cada documento tiene `id` y `fecha` (para ordenar); el resto lo define el módulo que lo guarda.
"""

from typing import Any

from google.api_core import exceptions as excepciones_google
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from app.integracion.errores import ErrorInfraestructura
from app.integracion.firestore import TIEMPO_LIMITE

Documento = dict[str, Any]
_ERRORES = (excepciones_google.GoogleAPIError, TimeoutError, OSError)


class RepositorioResultadosFirestore:
    def __init__(self, cliente: firestore.AsyncClient) -> None:
        self._cliente = cliente

    async def guardar(self, coleccion: str, documento: Documento) -> None:
        referencia = self._cliente.collection(coleccion).document(documento["id"])
        try:
            await referencia.create(documento, retry=None, timeout=TIEMPO_LIMITE)
        except _ERRORES as error:
            raise ErrorInfraestructura("firestore", type(error).__name__) from None

    async def obtener(self, coleccion: str, id_documento: str) -> Documento | None:
        try:
            foto = (
                await self._cliente.collection(coleccion)
                .document(id_documento)
                .get(retry=None, timeout=TIEMPO_LIMITE)
            )
        except _ERRORES as error:
            raise ErrorInfraestructura("firestore", type(error).__name__) from None
        return foto.to_dict() if foto.exists else None

    async def listar(
        self,
        coleccion: str,
        pagina: int,
        tamanio: int,
        igual_a: tuple[str, Any] | None = None,
    ) -> tuple[list[Documento], int]:
        """Página ordenada por `fecha` descendente y total de documentos que cumplen el filtro."""
        consulta: Any = self._cliente.collection(coleccion)
        if igual_a is not None:
            consulta = consulta.where(filter=FieldFilter(igual_a[0], "==", igual_a[1]))
        pagina_consulta = (
            consulta.order_by("fecha", direction=firestore.Query.DESCENDING)
            .offset(pagina * tamanio)
            .limit(tamanio)
        )
        try:
            fotos = await pagina_consulta.get(retry=None, timeout=TIEMPO_LIMITE)
            conteo = await consulta.count().get(retry=None, timeout=TIEMPO_LIMITE)
        except _ERRORES as error:
            raise ErrorInfraestructura("firestore", type(error).__name__) from None
        total = int(conteo[0][0].value)
        return [d for f in fotos if (d := f.to_dict()) is not None], total
