"""Historia 4: fallas de infraestructura (spec-trabajos.md)."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import aio_pika
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.cloud import firestore
from pydantic import SecretStr

from app.config import Configuracion
from app.trabajos.esquemas import Trabajo
from app.trabajos.registro import DefinicionTipo
from tests.conftest import RABBITMQ_URL
from tests.integration.conftest import agregar_ruta_crear_trabajo, esperar_rabbitmq


async def _sin_efecto(_: Trabajo) -> dict[str, Any]:
    return {}


def _ajustar(app: FastAPI) -> None:
    app.state.registro_tipos.registrar(DefinicionTipo("PRUEBA", _sin_efecto, timedelta(seconds=5)))
    agregar_ruta_crear_trabajo(app)


def test_rabbitmq_caido_al_crear_responde_503_y_deja_el_trabajo_fallido(
    crear_cliente: Callable[..., TestClient],
    configuracion_infra: Callable[..., Configuracion],
    proyecto_firestore: str,
    cabeceras_gerencia: dict[str, str],
) -> None:
    configuracion = configuracion_infra(rabbitmq_url=SecretStr("amqp://invalido.prueba:5672/"))
    cliente = crear_cliente(_ajustar, configuracion)

    respuesta = cliente.post(
        "/api/ia/v1/prueba/trabajos/PRUEBA", json={}, headers=cabeceras_gerencia
    )

    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "DEPENDENCIA_NO_DISPONIBLE"
    (documento,) = [
        d.to_dict()
        for d in firestore.Client(project=proyecto_firestore).collection("trabajos").get()
    ]
    assert documento["estado"] == "FALLIDO"
    assert documento["error"]["codigo"] == "COLA_NO_DISPONIBLE"


def test_readiness_informa_rabbitmq_caido_y_firestore_sano(
    crear_cliente: Callable[..., TestClient], configuracion_infra: Callable[..., Configuracion]
) -> None:
    configuracion = configuracion_infra(rabbitmq_url=SecretStr("amqp://invalido.prueba:5672/"))

    respuesta = crear_cliente(configuracion=configuracion).get("/salud/readiness")

    assert respuesta.status_code == 503
    assert respuesta.json()["componentes"] == {"firestore": "UP", "rabbitmq": "DOWN"}


def test_readiness_con_todo_sano(
    crear_cliente: Callable[..., TestClient], configuracion_infra: Callable[..., Configuracion]
) -> None:
    cliente = crear_cliente(configuracion=configuracion_infra())
    esperar_rabbitmq(cliente)

    respuesta = cliente.get("/salud/readiness")

    assert respuesta.status_code == 200
    assert respuesta.json()["componentes"] == {"firestore": "UP", "rabbitmq": "UP"}


async def _publicar_y_leer_dlq(cola: str, cuerpo: bytes) -> bytes | None:
    conexion = await aio_pika.connect(RABBITMQ_URL)
    async with conexion:
        canal = await conexion.channel()
        await canal.default_exchange.publish(aio_pika.Message(body=cuerpo), routing_key=cola)
        dlq = await canal.get_queue(f"{cola}.dlq")
        for _ in range(50):
            mensaje = await dlq.get(fail=False)
            if mensaje is not None:
                await mensaje.ack()
                return mensaje.body
            await asyncio.sleep(0.1)
    return None


def test_mensaje_mal_formado_termina_en_la_dlq(
    crear_cliente: Callable[..., TestClient],
    configuracion_infra: Callable[..., Configuracion],
    cola_trabajos: str,
) -> None:
    cliente = crear_cliente(_ajustar, configuracion_infra())
    esperar_rabbitmq(cliente)

    cuerpo = asyncio.run(_publicar_y_leer_dlq(cola_trabajos, b"esto no es un sobre"))

    assert cuerpo == b"esto no es un sobre"
