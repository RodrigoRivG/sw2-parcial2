"""ConexionRabbitMq contra el RabbitMQ de Docker Compose (spec-trabajos.md 2.6)."""

import json

import aio_pika
import pytest

from app.integracion.errores import ErrorInfraestructura
from app.integracion.rabbitmq import ConexionRabbitMq, crear_sobre
from tests.conftest import RABBITMQ_URL


async def test_declara_colas_y_publica_mensajes_persistentes(cola_trabajos: str) -> None:
    conexion = ConexionRabbitMq(RABBITMQ_URL, cola_trabajos)
    conexion.iniciar()
    try:
        await conexion.esperar_lista(10)
        sobre = crear_sobre("ProcesarTrabajo", {"idTrabajo": "abc"}, "corr-1")
        await conexion.publicar(cola_trabajos, sobre)

        lector = await aio_pika.connect(RABBITMQ_URL)
        async with lector:
            canal = await lector.channel()
            cola = await canal.get_queue(cola_trabajos)
            mensaje = await cola.get(timeout=5)
            await mensaje.ack()
            dlq = await canal.get_queue(f"{cola_trabajos}.dlq")
            assert dlq.name.endswith(".dlq")
    finally:
        await conexion.cerrar()

    assert json.loads(mensaje.body) == sobre
    assert mensaje.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
    assert mensaje.message_id == sobre["idMensaje"]
    assert mensaje.correlation_id == "corr-1"
    assert mensaje.content_type == "application/json"
    assert sobre["origen"] == "servicio-ia"
    assert sobre["version"] == 1


async def test_sin_conexion_publicar_falla_y_cerrar_no_se_cuelga() -> None:
    conexion = ConexionRabbitMq("amqp://invalido.prueba:5672/", "x")
    conexion.iniciar()

    with pytest.raises(ErrorInfraestructura):
        await conexion.publicar("x", crear_sobre("T", {}, None))
    with pytest.raises(ErrorInfraestructura):
        await conexion.comprobar()
    await conexion.cerrar()
