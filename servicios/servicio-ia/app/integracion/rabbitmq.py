"""Conexión a RabbitMQ: declaración de colas, publicación confirmada y canal de consumo.

Constitución §10 y README D-15. La conexión se intenta en segundo plano: si RabbitMQ no está
al arrancar, el servicio arranca igual (readiness en DOWN) y se conecta cuando vuelve.
"""

import asyncio
import contextlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractQueue, AbstractRobustConnection
from aio_pika.connection import make_url
from aio_pika.robust_connection import RobustConnection

from app.integracion.errores import ErrorInfraestructura

_logger = logging.getLogger("app.integracion.rabbitmq")
_TIEMPO_LIMITE_PUBLICACION = 3.0
_ESPERA_RECONEXION = 5.0


def crear_sobre(tipo: str, datos: dict[str, Any], id_correlacion: str | None) -> dict[str, Any]:
    """Sobre común de todos los mensajes del sistema (constitución §10)."""
    return {
        "idMensaje": str(uuid.uuid4()),
        "idCorrelacion": id_correlacion or str(uuid.uuid4()),
        "tipo": tipo,
        "version": 1,
        "fechaOcurrencia": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "origen": "servicio-ia",
        "datos": datos,
    }


class ConexionRabbitMq:
    def __init__(self, url: str, cola_trabajos: str) -> None:
        self._url = url
        self.cola_trabajos = cola_trabajos
        self._conexion: AbstractRobustConnection | None = None
        self._canal_publicacion: AbstractChannel | None = None
        self._lista = asyncio.Event()
        self._tarea: asyncio.Task[None] | None = None

    @property
    def cola_dlq(self) -> str:
        return f"{self.cola_trabajos}.dlq"

    @property
    def disponible(self) -> bool:
        return (
            self._conexion is not None
            and not self._conexion.is_closed
            and self._canal_publicacion is not None
            and not self._canal_publicacion.is_closed
        )

    def iniciar(self) -> None:
        self._tarea = asyncio.create_task(self._conectar(), name="conexion-rabbitmq")

    async def esperar_lista(self, tiempo_limite: float | None = None) -> None:
        await asyncio.wait_for(self._lista.wait(), tiempo_limite)

    async def _conectar(self) -> None:
        while True:
            # Se crea la conexión aparte de `connect` para poder cerrarla si el intento falla o
            # se cancela: `connect_robust` deja viva su tarea interna de reconexión en ese caso.
            conexion = RobustConnection(make_url(self._url))
            self._conexion = conexion
            try:
                await conexion.connect(timeout=5)
                canal = await conexion.channel(publisher_confirms=True)
                await self._declarar(canal)
            except BaseException as error:
                await self._cerrar_conexion()
                if not isinstance(error, Exception):
                    raise  # cancelación del apagado
                _logger.warning(
                    "RabbitMQ no disponible; se reintenta",
                    extra={"motivo": type(error).__name__},
                )
                await asyncio.sleep(_ESPERA_RECONEXION)
                continue
            self._canal_publicacion = canal
            self._lista.set()
            _logger.info("Conectado a RabbitMQ")
            return

    async def _declarar(self, canal: AbstractChannel) -> None:
        await canal.declare_queue(self.cola_dlq, durable=True)
        await canal.declare_queue(
            self.cola_trabajos,
            durable=True,
            arguments={"x-dead-letter-exchange": "", "x-dead-letter-routing-key": self.cola_dlq},
        )

    async def publicar(self, cola: str, sobre: dict[str, Any]) -> None:
        if not self.disponible or self._canal_publicacion is None:
            raise ErrorInfraestructura("rabbitmq", "sin conexión")
        mensaje = aio_pika.Message(
            body=json.dumps(sobre, ensure_ascii=False).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=sobre["idMensaje"],
            correlation_id=sobre["idCorrelacion"],
            type=sobre["tipo"],
        )
        try:
            await asyncio.wait_for(
                self._canal_publicacion.default_exchange.publish(mensaje, routing_key=cola),
                _TIEMPO_LIMITE_PUBLICACION,
            )
        except Exception as error:
            raise ErrorInfraestructura("rabbitmq", type(error).__name__) from None

    async def cola_de_consumo(self, prefetch: int) -> AbstractQueue:
        """Canal propio para consumir la cola de trabajos, con `prefetch` mensajes a la vez."""
        await self._lista.wait()
        assert self._conexion is not None
        canal = await self._conexion.channel()
        await canal.set_qos(prefetch_count=prefetch)
        return await canal.get_queue(self.cola_trabajos, ensure=True)

    async def comprobar(self) -> None:
        if not self.disponible:
            raise ErrorInfraestructura("rabbitmq", "sin conexión")

    async def cerrar(self) -> None:
        if self._tarea is not None and not self._tarea.done():
            self._tarea.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._tarea
        await self._cerrar_conexion()

    async def _cerrar_conexion(self) -> None:
        conexion, self._conexion, self._canal_publicacion = self._conexion, None, None
        if conexion is not None:
            with contextlib.suppress(Exception):
                await asyncio.shield(conexion.close())
