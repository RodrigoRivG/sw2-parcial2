"""Manejador `CONSULTA_AGENTE` (spec-agentes.md 2.7, historias 1 y 3, RQ-AGE-09)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from app.agentes import servicio as modulo_servicio
from app.agentes.servicio import AVISO, ServicioAgentes
from app.comun.errores import ErrorAplicacion
from app.comun.seguridad import UsuarioAutenticado
from app.integracion.gateway import ClienteGateway
from app.integracion.modelo_lenguaje import ModeloLenguajeNoDisponible
from app.mcp_server.servidor import crear_servidor_mcp
from app.trabajos.esquemas import Trabajo
from app.trabajos.estados import EstadoTrabajo
from tests.modelo_guion import ModeloGuion, agente, herramientas, texto
from tests.unit.mcp_server.conftest import Servicios, TokenFijo, ejemplo

PREGUNTA = "¿Qué insumos de Finca Secreta están bajo el mínimo?"
GERENCIA = UsuarioAutenticado("ger", "Gerencia", frozenset({"gerencia"}))


class TrabajosFijos:
    def __init__(self) -> None:
        self.creados: list[tuple[str, dict[str, Any], str]] = []

    async def crear(self, tipo: str, parametros: dict[str, Any], solicitante: Any) -> str:
        self.creados.append((tipo, parametros, solicitante.id))
        return "trabajo"


def _trabajo() -> Trabajo:
    return Trabajo(
        id="t1",
        tipo="CONSULTA_AGENTE",
        estado=EstadoTrabajo.PROCESANDO,
        id_solicitante="ger",
        id_correlacion=None,
        parametros={"pregunta": PREGUNTA},
        fecha_creacion=datetime.now(UTC),
    )


@asynccontextmanager
async def _servicio(modelo: ModeloGuion) -> AsyncIterator[tuple[ServicioAgentes, TrabajosFijos]]:
    servicios = Servicios()
    servicios.json(
        "/api/inventario/v1/estado-inventario", {**ejemplo("estado_inventario"), "total": 1}
    )
    trabajos = TrabajosFijos()
    async with httpx.AsyncClient(transport=httpx.MockTransport(servicios)) as http:
        gateway = ClienteGateway(http, "http://gateway.prueba", TokenFijo(), 1.0)
        yield ServicioAgentes(modelo, crear_servidor_mcp(gateway), trabajos), trabajos  # type: ignore[arg-type]


async def test_resultado_del_trabajo_y_logs_sin_pregunta_ni_datos(
    caplog: pytest.LogCaptureFixture,
) -> None:
    modelo = ModeloGuion(
        agente("inventario"),
        herramientas(("consultar_estado_inventario", {"soloStockBajo": True})),
        texto(""),
        texto("Glifosato tiene 20 litros. El promedio es 7,5 litros."),
    )
    caplog.set_level(logging.DEBUG)

    async with _servicio(modelo) as (servicio, _):
        resultado = await servicio.procesar(_trabajo())

    assert resultado["pregunta"] == PREGUNTA
    assert resultado["agente"] == "inventario"
    assert resultado["respuesta"] == "Glifosato tiene 20 litros."
    assert resultado["cifrasOmitidas"] == 1
    (herramienta,) = resultado["herramientas"]
    assert herramienta["nombre"] == "consultar_estado_inventario"
    assert herramienta["argumentos"] == {"soloStockBajo": True}
    assert herramienta["error"] is None and herramienta["duracionMs"] >= 0
    assert resultado["datos"][0]["herramienta"] == "consultar_estado_inventario"
    assert resultado["datos"][0]["resultado"]["items"][0]["nombre"] == "Glifosato"
    assert resultado["modeloLenguaje"] == "modelo-guion"
    assert resultado["aviso"] == AVISO

    registro = [r for r in caplog.records if r.getMessage() == "Consulta de agente atendida"]
    assert registro and registro[0].agente == "inventario"  # type: ignore[attr-defined]
    for r in caplog.records:
        contenido = r.getMessage() + repr(r.__dict__)
        assert "Finca Secreta" not in contenido and "Glifosato" not in contenido


async def test_modelo_caido_durante_la_consulta() -> None:
    async with _servicio(ModeloGuion(ModeloLenguajeNoDisponible())) as (servicio, _):
        with pytest.raises(ErrorAplicacion) as error:
            await servicio.procesar(_trabajo())

    assert error.value.codigo == "MODELO_LENGUAJE_NO_DISPONIBLE"
    assert "no está disponible" in error.value.mensaje


async def test_limite_de_pasos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo_servicio, "MAXIMO_PASOS", 3)
    modelo = ModeloGuion(
        agente("inventario"), herramientas(("consultar_estado_inventario", {})), repetir=True
    )

    async with _servicio(modelo) as (servicio, _):
        with pytest.raises(ErrorAplicacion) as error:
            await servicio.procesar(_trabajo())

    assert error.value.codigo == "LIMITE_PASOS_AGENTE"
    assert "más pasos de los permitidos" in error.value.mensaje


async def test_solicitar_falla_rapido_si_ollama_esta_caido() -> None:
    async with _servicio(ModeloGuion(disponible=False)) as (servicio, trabajos):
        with pytest.raises(ErrorAplicacion) as error:
            await servicio.solicitar("¿Qué insumos hay?", GERENCIA)

    assert (error.value.estado_http, error.value.codigo) == (503, "MODELO_LENGUAJE_NO_DISPONIBLE")
    assert trabajos.creados == []


async def test_solicitar_crea_el_trabajo() -> None:
    async with _servicio(ModeloGuion()) as (servicio, trabajos):
        await servicio.solicitar("¿Qué insumos hay?", GERENCIA)

    assert trabajos.creados == [("CONSULTA_AGENTE", {"pregunta": "¿Qué insumos hay?"}, "ger")]
