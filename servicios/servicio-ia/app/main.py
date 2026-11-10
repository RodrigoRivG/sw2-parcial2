"""Punto de entrada: `uvicorn --factory app.main:crear_app`."""

import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from importlib.metadata import version

import httpx
from fastapi import FastAPI

from app.agentes.router import router_agentes
from app.agentes.servicio import TIEMPO_LIMITE as TIEMPO_LIMITE_CONSULTA
from app.agentes.servicio import TIPO_TRABAJO as TIPO_TRABAJO_CONSULTA
from app.agentes.servicio import ServicioAgentes
from app.comun.correlacion import MiddlewareCorrelacion
from app.comun.errores import error_interno_asgi, registrar_manejadores
from app.comun.logs import configurar_logs
from app.comun.salud import RegistroSalud, router_salud
from app.comun.seguridad import ProveedorClavesJwks
from app.config import Configuracion, ConfiguracionInvalida, cargar_configuracion
from app.integracion.almacen_archivos import AlmacenS3
from app.integracion.datos_agricolas import DatosAgricolasGateway
from app.integracion.gateway import ClienteGateway
from app.integracion.modelo_lenguaje import ModeloOllama
from app.integracion.mongodb import comprobar_mongo, crear_cliente_mongo
from app.integracion.rabbitmq import ConexionRabbitMq
from app.integracion.repositorio_resultados import RepositorioResultadosMongo
from app.integracion.repositorio_trabajos import RepositorioTrabajosMongo
from app.integracion.repositorio_versiones import RepositorioVersionesMongo
from app.integracion.token_servicio import TokenCuentaServicio
from app.integracion.transcriptor import TranscriptorWhisper
from app.mcp_server.http import RUTA as RUTA_MCP
from app.mcp_server.http import EndpointMcp, preparar_http
from app.mcp_server.servidor import crear_servidor_mcp
from app.modelos.cargador import CargadorModelos
from app.modelos.router import router_modelos
from app.modelos.servicio import ServicioModelos
from app.prediccion.router import router_prediccion
from app.prediccion.servicio import MODELO_PATRONES, MODELO_RENDIMIENTO, ServicioPrediccion
from app.reportes.router import router_reportes
from app.reportes.servicio import TIEMPO_LIMITE as TIEMPO_LIMITE_REPORTE
from app.reportes.servicio import TIPO_TRABAJO as TIPO_TRABAJO_REPORTE
from app.reportes.servicio import ServicioReportes
from app.trabajos.consumidor import ConsumidorTrabajos
from app.trabajos.registro import DefinicionTipo, RegistroTipos
from app.trabajos.revision import RevisionPeriodica
from app.trabajos.router import router_trabajos
from app.trabajos.servicio import ServicioTrabajos
from app.vision.router import router_vision
from app.vision.servicio import (
    MODELO as MODELO_CLASIFICADOR,
)
from app.vision.servicio import (
    TIEMPO_LIMITE_VIDEO,
    TIPO_TRABAJO_VIDEO,
    ServicioVision,
    deserializar_keras,
)

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
        async with (
            httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0)) as cliente,
            AsyncExitStack() as pila,
        ):
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
            cliente_mongo = crear_cliente_mongo(config.mongodb_uri.get_secret_value())
            base_mongo = cliente_mongo[config.mongodb_base]
            repositorio = RepositorioTrabajosMongo(base_mongo)
            conexion = ConexionRabbitMq(
                config.rabbitmq_url.get_secret_value(), config.trabajos_cola
            )
            conexion.iniciar()
            app.state.base_mongo = base_mongo
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
            almacen = AlmacenS3(config.aws_bucket, config.s3_prefijo, config.aws_endpoint)
            cargador = CargadorModelos(
                RepositorioVersionesMongo(base_mongo),
                almacen,
                config.modelos_intervalo_revision_segundos,
            )
            for nombre in MODELOS:
                cargador.registrar(nombre)
            cargador.registrar(MODELO_CLASIFICADOR, deserializar_keras, "modelo.keras")
            cargador.iniciar()
            app.state.almacen_archivos = almacen
            app.state.cargador_modelos = cargador
            app.state.servicio_modelos = ServicioModelos(
                RepositorioVersionesMongo(base_mongo), cargador
            )
            app.state.servicio_prediccion = ServicioPrediccion(
                DatosAgricolasGateway(app.state.cliente_gateway),
                cargador,
                RepositorioResultadosMongo(base_mongo),
            )

            # Visión (spec-vision.md)
            app.state.servicio_vision = ServicioVision(
                cargador,
                RepositorioResultadosMongo(base_mongo),
                almacen,
                app.state.servicio_trabajos,
            )

            # Herramientas MCP y agentes (spec-agentes.md)
            servidor_mcp = crear_servidor_mcp(app.state.cliente_gateway)
            app.state.mcp_http, gestor_mcp = preparar_http(servidor_mcp)
            await pila.enter_async_context(gestor_mcp)
            app.state.modelo_lenguaje = ModeloOllama(
                config.ollama_base_url, config.ollama_model, config.agentes_num_ctx
            )
            app.state.servicio_agentes = ServicioAgentes(
                app.state.modelo_lenguaje, servidor_mcp, app.state.servicio_trabajos
            )

            # Reportes (spec-reportes.md)
            transcriptor = TranscriptorWhisper(
                config.whisper_model,
                config.whisper_device,
                config.whisper_compute_type,
                config.whisper_carpeta,
            )
            transcriptor.iniciar(config.whisper_activo)
            app.state.transcriptor = transcriptor
            app.state.servicio_reportes = ServicioReportes(
                app.state.modelo_lenguaje,
                servidor_mcp,
                app.state.servicio_trabajos,
                almacen,
                conexion,
                transcriptor,
                config.reportes_retencion_dias,
            )

            _logger.info("Servicio iniciado")
            try:
                yield
            finally:
                await cargador.detener()
                await transcriptor.detener()
                await consumidor.detener()
                await revision.detener()
                await conexion.cerrar()
                await cliente_mongo.close()
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
        "mongodb", lambda: comprobar_mongo(app.state.base_mongo), critica=True
    )
    app.state.registro_salud.registrar(
        "rabbitmq", lambda: app.state.conexion_rabbitmq.comprobar(), critica=True
    )
    registro_tipos.registrar(
        DefinicionTipo(
            TIPO_TRABAJO_VIDEO,
            lambda trabajo: app.state.servicio_vision.procesar_video(trabajo),
            TIEMPO_LIMITE_VIDEO,
        )
    )
    registro_tipos.registrar(
        DefinicionTipo(
            TIPO_TRABAJO_CONSULTA,
            lambda trabajo: app.state.servicio_agentes.procesar(trabajo),
            TIEMPO_LIMITE_CONSULTA,
        )
    )
    app.state.registro_salud.registrar(
        "ollama", lambda: app.state.modelo_lenguaje.comprobar(), critica=False
    )
    registro_tipos.registrar(
        DefinicionTipo(
            TIPO_TRABAJO_REPORTE,
            lambda trabajo: app.state.servicio_reportes.procesar(trabajo),
            TIEMPO_LIMITE_REPORTE,
        )
    )
    app.state.registro_salud.registrar(
        "whisper", lambda: app.state.transcriptor.comprobar(), critica=False
    )
    for nombre in (*MODELOS, MODELO_CLASIFICADOR):
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
    app.include_router(router_vision)
    app.include_router(router_agentes)
    app.include_router(router_reportes)
    app.router.add_route(
        RUTA_MCP,
        EndpointMcp(lambda: app.state),  # type: ignore[arg-type]
        methods=["GET", "POST", "DELETE"],
        include_in_schema=False,
    )
    return app
