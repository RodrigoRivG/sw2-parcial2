"""Punto de entrada: `uvicorn --factory app.main:crear_app`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

import httpx
from fastapi import FastAPI

from app.comun.correlacion import MiddlewareCorrelacion
from app.comun.errores import error_interno_asgi, registrar_manejadores
from app.comun.logs import configurar_logs
from app.comun.salud import RegistroSalud, router_salud
from app.comun.seguridad import ProveedorClavesJwks
from app.config import Configuracion, ConfiguracionInvalida, cargar_configuracion
from app.integracion.gateway import ClienteGateway
from app.integracion.token_servicio import TokenCuentaServicio

_logger = logging.getLogger("app")


def crear_app(configuracion: Configuracion | None = None) -> FastAPI:
    if configuracion is None:
        try:
            configuracion = cargar_configuracion()
        except ConfiguracionInvalida as error:
            configurar_logs()
            _logger.error(str(error), extra={"variables": error.variables})
            raise SystemExit(1) from None
    configurar_logs(configuracion.nivel_log)
    config = configuracion

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0)) as cliente:
            token = TokenCuentaServicio(
                cliente,
                config.keycloak_token_url,
                config.keycloak_client_id,
                config.keycloak_client_secret.get_secret_value(),
            )
            app.state.cliente_http = cliente
            app.state.proveedor_claves = ProveedorClavesJwks(cliente, config.keycloak_jwks_uri)
            app.state.token_servicio = token
            app.state.cliente_gateway = ClienteGateway(
                cliente, config.api_gateway_url, token, config.gateway_tiempo_limite_segundos
            )
            _logger.info("Servicio iniciado")
            yield
        _logger.info("Servicio detenido")

    app = FastAPI(
        title="servicio-ia",
        version=version("servicio-ia"),
        description="Servicio de inteligencia artificial del sistema de campañas agrícolas.",
        lifespan=ciclo_de_vida,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url=None,
    )
    app.state.configuracion = config
    app.state.registro_salud = RegistroSalud()
    app.add_middleware(MiddlewareCorrelacion, error_interno=error_interno_asgi)
    registrar_manejadores(app)
    app.include_router(router_salud)
    return app
