"""Identificador de correlación y log de acceso (README D-09 y D-10, RNF-22)."""

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

ENCABEZADO = "X-Correlation-Id"
_PATRON = re.compile(r"^[A-Za-z0-9-]{1,64}$")

id_correlacion_actual: ContextVar[str | None] = ContextVar("id_correlacion", default=None)

_logger = logging.getLogger("app.acceso")

Scope = dict[str, Any]
Mensaje = dict[str, Any]
Recibir = Callable[[], Awaitable[Mensaje]]
Enviar = Callable[[Mensaje], Awaitable[None]]
AplicacionAsgi = Callable[[Scope, Recibir, Enviar], Awaitable[None]]
GeneradorError500 = Callable[[], tuple[int, list[tuple[bytes, bytes]], bytes]]


def normalizar_id(valor: str | None) -> str:
    """Devuelve el id recibido si es válido; si no, uno nuevo."""
    if valor and _PATRON.match(valor):
        return valor
    return str(uuid.uuid4())


class MiddlewareCorrelacion:
    """Middleware ASGI puro, el más externo de la aplicación.

    Pone el id en el contexto y en la respuesta, escribe el log de acceso y, si la
    aplicación lanza una excepción no manejada, responde el 500 común con el mismo id.
    """

    def __init__(self, app: AplicacionAsgi, error_interno: GeneradorError500) -> None:
        self.app = app
        self.error_interno = error_interno

    async def __call__(self, scope: Scope, receive: Recibir, send: Enviar) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        recibido = None
        for nombre, valor in scope.get("headers", []):
            if nombre.lower() == ENCABEZADO.lower().encode():
                recibido = valor.decode("latin-1")
                break
        id_correlacion = normalizar_id(recibido)
        token = id_correlacion_actual.set(id_correlacion)
        estado_solicitud = scope.setdefault("state", {})
        inicio = time.perf_counter()
        estado_http = 500
        respuesta_iniciada = False

        async def enviar(mensaje: Mensaje) -> None:
            nonlocal estado_http, respuesta_iniciada
            if mensaje["type"] == "http.response.start":
                respuesta_iniciada = True
                estado_http = mensaje["status"]
                encabezados = [
                    (k, v)
                    for k, v in mensaje.get("headers", [])
                    if k.lower() != b"x-correlation-id"
                ]
                encabezados.append((ENCABEZADO.encode(), id_correlacion.encode()))
                mensaje = {**mensaje, "headers": encabezados}
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        except Exception:
            logging.getLogger("app.errores").exception("Error no controlado")
            if respuesta_iniciada:
                raise
            estado, encabezados, cuerpo = self.error_interno()
            await enviar({"type": "http.response.start", "status": estado, "headers": encabezados})
            await enviar({"type": "http.response.body", "body": cuerpo})
        finally:
            _logger.info(
                "solicitud atendida",
                extra={
                    "metodo": scope.get("method"),
                    "ruta": scope.get("path"),
                    "estado": estado_http,
                    "duracionMs": round((time.perf_counter() - inicio) * 1000, 1),
                    "sub": estado_solicitud.get("sub"),
                },
            )
            id_correlacion_actual.reset(token)
