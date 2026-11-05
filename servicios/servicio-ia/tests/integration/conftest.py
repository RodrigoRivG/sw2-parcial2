"""Infraestructura real para los tests de integración (spec-trabajos.md 2.13).

Cada test usa un proyecto de Firestore y colas propias, que se borran al terminar, para no
chocar con el servicio que esté corriendo en Docker Compose.
"""

import asyncio
import os
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import aio_pika
import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.comun.errores import respuestas_error
from app.comun.esquemas import ModeloEntrada
from app.comun.seguridad import UsuarioAutenticado, router_protegido, usuario_actual
from app.config import Configuracion
from app.trabajos.servicio import ServicioTrabajos, respuesta_creado, servicio_trabajos
from tests.conftest import RABBITMQ_URL, autorizacion, configuracion_de_prueba, emitir_token

EMULADOR_FIRESTORE = os.environ["FIRESTORE_EMULATOR_HOST"]


@pytest.fixture
def proyecto_firestore() -> Iterator[str]:
    proyecto = f"pruebas-{uuid.uuid4().hex[:12]}"
    yield proyecto
    httpx.delete(
        f"http://{EMULADOR_FIRESTORE}/emulator/v1/projects/{proyecto}/databases/(default)/documents",
        timeout=10,
    )


async def _borrar_colas(nombres: list[str]) -> None:
    conexion = await aio_pika.connect(RABBITMQ_URL, timeout=5)
    async with conexion:
        canal = await conexion.channel()
        for nombre in nombres:
            await canal.queue_delete(nombre)


@pytest.fixture
def cola_trabajos() -> Iterator[str]:
    cola = f"pruebas-{uuid.uuid4().hex[:8]}.servicio-ia.trabajos"
    yield cola
    asyncio.run(_borrar_colas([cola, f"{cola}.dlq"]))


@pytest.fixture
def configuracion_infra(
    proyecto_firestore: str, cola_trabajos: str
) -> Callable[..., Configuracion]:
    def crear(**cambios: Any) -> Configuracion:
        valores: dict[str, Any] = {
            "google_cloud_project": proyecto_firestore,
            "rabbitmq_url": SecretStr(RABBITMQ_URL),
            "trabajos_cola": cola_trabajos,
            "trabajos_consumidor_activo": True,
        }
        valores.update(cambios)
        return configuracion_de_prueba(**valores)

    return crear


class CuerpoTrabajoPrueba(ModeloEntrada):
    parametros: dict[str, Any] = {}


def agregar_ruta_crear_trabajo(app: FastAPI) -> None:
    """`POST /api/ia/v1/prueba/trabajos/{tipo}`: crea un trabajo de ese tipo (solo en tests)."""
    router = router_protegido(tags=["prueba"])

    @router.post("/prueba/trabajos/{tipo}", responses=respuestas_error(400, 401, 403, 500, 503))
    async def crear(
        tipo: str,
        cuerpo: CuerpoTrabajoPrueba,
        usuario: UsuarioAutenticado = Depends(usuario_actual),
        servicio: ServicioTrabajos = Depends(servicio_trabajos),
    ) -> Any:
        trabajo = await servicio.crear(tipo, cuerpo.parametros, usuario)
        return respuesta_creado(trabajo)

    app.include_router(router)


def esperar_estado_final(
    cliente: TestClient, id_trabajo: str, cabeceras: dict[str, str], tiempo_limite: float = 10.0
) -> dict[str, Any]:
    fin = time.monotonic() + tiempo_limite
    while time.monotonic() < fin:
        respuesta = cliente.get(f"/api/ia/v1/trabajos/{id_trabajo}", headers=cabeceras)
        cuerpo: dict[str, Any] = respuesta.json()
        if cuerpo.get("estado") in ("COMPLETADO", "FALLIDO"):
            return cuerpo
        time.sleep(0.05)
    raise AssertionError(f"El trabajo {id_trabajo} no terminó en {tiempo_limite} s")


def esperar_rabbitmq(cliente: TestClient, tiempo_limite: float = 15.0) -> None:
    """Espera a que la conexión de fondo a RabbitMQ esté lista."""
    fin = time.monotonic() + tiempo_limite
    while time.monotonic() < fin:
        if cliente.get("/salud/readiness").json()["componentes"].get("rabbitmq") == "UP":
            return
        time.sleep(0.1)
    raise AssertionError("RabbitMQ no quedó disponible")


@pytest.fixture
def cabeceras_gerencia() -> dict[str, str]:
    return autorizacion(emitir_token(["gerencia"], sub="ana"))
