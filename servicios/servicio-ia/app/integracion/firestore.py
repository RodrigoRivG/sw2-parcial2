"""Cliente de Firestore compartido (usa el emulador si existe FIRESTORE_EMULATOR_HOST)."""

from google.cloud import firestore

TIEMPO_LIMITE = 5.0


def crear_cliente_firestore(proyecto: str) -> firestore.AsyncClient:
    return firestore.AsyncClient(project=proyecto)


async def comprobar_firestore(cliente: firestore.AsyncClient) -> None:
    """Comprobación de salud: una lectura mínima."""
    consulta = cliente.collection("trabajos").limit(1)
    await consulta.get(retry=None, timeout=TIEMPO_LIMITE)
