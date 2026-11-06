"""Publicación del servidor MCP en `/api/ia/v1/mcp` para gerencia (spec-agentes.md 2.3, RQ-AGE-07).

*Streamable HTTP* sin estado y con respuestas JSON. La ruta no pasa por las dependencias de
FastAPI: este ASGI valida el JWT y el rol con las mismas funciones que el resto del servicio.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp
from starlette.types import ASGIApp, Receive, Scope, Send

from app.comun.errores import ErrorAplicacion, respuesta_error
from app.comun.seguridad import PREFIJO_API, ProveedorClavesJwks, validar_token

RUTA = f"{PREFIJO_API}/mcp"
ROLES = ("gerencia",)


def preparar_http(servidor: MCPServer) -> tuple[ASGIApp, AbstractAsyncContextManager[None]]:
    """El ASGI del transporte y el contexto que mantiene vivo su gestor (para el `lifespan`).

    `host="0.0.0.0"` desactiva la protección contra *DNS rebinding* del SDK, pensada para un
    servidor local sin autenticación: aquí las solicitudes llegan por el gateway y con JWT.
    """
    servidor.streamable_http_app(stateless_http=True, json_response=True, host="0.0.0.0")
    gestor = servidor.session_manager
    return StreamableHTTPASGIApp(gestor), gestor.run()


class EndpointMcp:
    """ASGI de la ruta: autentica y delega en el transporte creado en el `lifespan`."""

    def __init__(self, estado: Callable[[], Any]) -> None:
        self._estado = estado

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        estado = self._estado()
        token = _bearer(scope)
        try:
            if token is None:
                raise ErrorAplicacion(401, "NO_AUTENTICADO")
            proveedor: ProveedorClavesJwks = estado.proveedor_claves
            usuario = await validar_token(token, proveedor, estado.configuracion)
            if not usuario.tiene_alguno(*ROLES):
                raise ErrorAplicacion(403, "SIN_PERMISO")
        except ErrorAplicacion as error:
            await respuesta_error(error.estado_http, error.codigo)(scope, receive, send)
            return
        scope.setdefault("state", {})["sub"] = usuario.id
        transporte: ASGIApp = estado.mcp_http
        await transporte(scope, receive, send)


def _bearer(scope: Scope) -> str | None:
    for nombre, valor in scope.get("headers", []):
        if nombre == b"authorization":
            esquema, _, token = valor.decode("latin-1").partition(" ")
            return token.strip() or None if esquema.lower() == "bearer" else None
    return None
