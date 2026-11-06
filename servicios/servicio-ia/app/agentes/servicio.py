"""Consultas a los agentes como trabajo `CONSULTA_AGENTE` (spec-agentes.md 2.7, RQ-AGE-01 y 09)."""

import logging
from datetime import timedelta
from typing import Any

from fastapi import Request
from langgraph.errors import GraphRecursionError
from mcp import Client
from mcp.server.mcpserver import MCPServer

from app.agentes.estado import MAXIMO_PASOS, TIEMPO_LIMITE_CONSULTA, EstadoAgente
from app.agentes.grafo import construir_grafo
from app.comun.errores import ErrorAplicacion
from app.comun.seguridad import UsuarioAutenticado
from app.integracion.modelo_lenguaje import ModeloLenguaje, ModeloLenguajeNoDisponible
from app.trabajos.esquemas import Trabajo
from app.trabajos.servicio import ServicioTrabajos

TIPO_TRABAJO = "CONSULTA_AGENTE"
TIEMPO_LIMITE = timedelta(seconds=TIEMPO_LIMITE_CONSULTA)
MENSAJE_NO_DISPONIBLE = "El asistente no está disponible en este momento. Intente más tarde."
MENSAJE_LIMITE_PASOS = (
    "La consulta necesitó más pasos de los permitidos. Intente una pregunta más concreta."
)
AVISO = (
    "Respuesta redactada por un modelo de lenguaje a partir de los datos consultados. "
    "Las cifras se verificaron contra esos datos."
)
_logger = logging.getLogger("app.agentes")


def _no_disponible() -> ErrorAplicacion:
    return ErrorAplicacion(503, "MODELO_LENGUAJE_NO_DISPONIBLE", MENSAJE_NO_DISPONIBLE)


class ServicioAgentes:
    def __init__(
        self, modelo: ModeloLenguaje, servidor_mcp: MCPServer, trabajos: ServicioTrabajos
    ) -> None:
        self._modelo = modelo
        self._servidor_mcp = servidor_mcp
        self._trabajos = trabajos

    async def solicitar(self, pregunta: str, solicitante: UsuarioAutenticado) -> Trabajo:
        """Falla rápido si la última comprobación dice que Ollama está caído (RQ-AGE-08)."""
        if not await self._modelo.disponible():
            raise _no_disponible()
        return await self._trabajos.crear(TIPO_TRABAJO, {"pregunta": pregunta}, solicitante)

    async def procesar(self, trabajo: Trabajo) -> dict[str, Any]:
        """Manejador del trabajo: una sesión MCP en memoria y un grafo por consulta."""
        pregunta = str(trabajo.parametros["pregunta"])
        fallo: ErrorAplicacion | None = None
        async with Client(self._servidor_mcp) as sesion:
            herramientas = (await sesion.list_tools()).tools
            grafo = construir_grafo(self._modelo, sesion, herramientas)
            # Se captura dentro: el Client usa un grupo de tareas y, desde afuera, la excepción
            # llegaría envuelta en un ExceptionGroup.
            try:
                estado: EstadoAgente = await grafo.ainvoke(
                    {"pregunta": pregunta, "llamadas": []},
                    {"recursion_limit": MAXIMO_PASOS},
                )
            except ModeloLenguajeNoDisponible:
                fallo = _no_disponible()
            except GraphRecursionError:
                _logger.warning("Consulta sin terminar al límite de pasos")
                fallo = ErrorAplicacion(500, "LIMITE_PASOS_AGENTE", MENSAJE_LIMITE_PASOS)
        if fallo is not None:
            raise fallo

        llamadas = estado.get("llamadas", [])
        # Sin la pregunta ni los datos (RQ-AGE-09).
        _logger.info(
            "Consulta de agente atendida",
            extra={
                "agente": estado["agente"],
                "herramientas": [
                    {
                        "nombre": ll["nombre"],
                        "duracionMs": ll["duracionMs"],
                        "fallo": bool(ll["error"]),
                    }
                    for ll in llamadas
                ],
                "cifrasOmitidas": estado.get("cifrasOmitidas", 0),
            },
        )
        return {
            "pregunta": pregunta,
            "agente": estado["agente"],
            "respuesta": estado.get("respuesta", ""),
            "herramientas": [
                {
                    "nombre": ll["nombre"],
                    "argumentos": ll["argumentos"],
                    "duracionMs": ll["duracionMs"],
                    "error": ll["error"],
                }
                for ll in llamadas
            ],
            "datos": [
                {"herramienta": ll["nombre"], "resultado": ll["resultado"]}
                for ll in llamadas
                if ll["error"] is None
            ],
            "cifrasOmitidas": estado.get("cifrasOmitidas", 0),
            "modeloLenguaje": self._modelo.nombre,
            "aviso": AVISO,
        }


def servicio_agentes(request: Request) -> ServicioAgentes:
    servicio: ServicioAgentes = request.app.state.servicio_agentes
    return servicio
