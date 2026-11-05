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
from app.integracion.almacen_archivos import AlmacenGcs
from app.integracion.datos_agricolas import DatosAgricolasGateway
from app.integracion.firestore import comprobar_firestore, crear_cliente_firestore
from app.integracion.gateway import ClienteGateway
from app.integracion.rabbitmq import ConexionRabbitMq
from app.integracion.repositorio_resultados import RepositorioResultadosFirestore
from app.integracion.repositorio_trabajos import RepositorioTrabajosFirestore
from app.integracion.repositorio_versiones import RepositorioVersionesFirestore
from app.integracion.token_servicio import TokenCuentaServicio
from app.modelos.cargador import CargadorModelos
from app.modelos.router import router_modelos
from app.modelos.servicio import ServicioModelos
from app.prediccion.router import router_prediccion
from app.prediccion.servicio import MODELO_PATRONES, MODELO_RENDIMIENTO, ServicioPrediccion
from app.trabajos.consumidor import ConsumidorTrabajos
from app.trabajos.registro import RegistroTipos
from app.trabajos.revision import RevisionPeriodica
from app.trabajos.router import router_trabajos
from app.trabajos.servicio import ServicioTrabajos

_logger = logging.getLogger("app")
MODELOS = (MODELO_RENDIMIENTO, MODELO_PATRONES)


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

            # Trabajos asíncronos (spec-trabajos.md)
            firestore = crear_cliente_firestore(config.google_cloud_project)
            repositorio = RepositorioTrabajosFirestore(firestore)
            conexion = ConexionRabbitMq(
                config.rabbitmq_url.get_secret_value(), config.trabajos_cola
            )
            conexion.iniciar()
            app.state.cliente_firestore = firestore
            app.state.conexion_rabbitmq = conexion
            app.state.servicio_trabajos = ServicioTrabajos(
                repositorio, conexion, registro_tipos, config.trabajos_retencion_dias
            )
            consumidor = ConsumidorTrabajos(
                repositorio, registro_tipos, config.trabajos_retencion_dias
            )
            revision = RevisionPeriodica(repositorio, config.trabajos_retencion_dias)
            if config.trabajos_consumidor_activo:
                consumidor.iniciar(conexion, config.trabajos_concurrencia)
                revision.iniciar()

            # Modelos y predicción (spec-prediccion.md)
            almacen = AlmacenGcs(config.google_cloud_project, config.gcs_bucket)
            cargador = CargadorModelos(
                RepositorioVersionesFirestore(firestore),
                almacen,
                config.modelos_intervalo_revision_segundos,
            )
            for nombre in MODELOS:
                cargador.registrar(nombre)
            cargador.iniciar()
            app.state.almacen_archivos = almacen
            app.state.cargador_modelos = cargador
            app.state.servicio_modelos = ServicioModelos(
                RepositorioVersionesFirestore(firestore), cargador
            )
            app.state.servicio_prediccion = ServicioPrediccion(
                DatosAgricolasGateway(app.state.cliente_gateway),
                cargador,
                RepositorioResultadosFirestore(firestore),
            )

            _logger.info("Servicio iniciado")
            try:
                yield
            finally:
                await cargador.detener()
                await consumidor.detener()
                await revision.detener()
                await conexion.cerrar()
                firestore.close()  # type: ignore[no-untyped-call]
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
    registro_tipos = RegistroTipos()
    app.state.configuracion = config
    app.state.registro_tipos = registro_tipos
    app.state.registro_salud = RegistroSalud()
    app.state.registro_salud.registrar(
        "firestore", lambda: comprobar_firestore(app.state.cliente_firestore), critica=True
    )
    app.state.registro_salud.registrar(
        "rabbitmq", lambda: app.state.conexion_rabbitmq.comprobar(), critica=True
    )
    for nombre in MODELOS:
        app.state.registro_salud.registrar(
            f"modelo_{nombre}",
            lambda n=nombre: app.state.cargador_modelos.comprobar(n),
            critica=False,
        )
    app.add_middleware(MiddlewareCorrelacion, error_interno=error_interno_asgi)
    registrar_manejadores(app)
    app.include_router(router_salud)
    app.include_router(router_trabajos)
    app.include_router(router_modelos)
    app.include_router(router_prediccion)
    return app
