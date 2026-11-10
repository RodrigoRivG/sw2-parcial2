"""Historia 1 y Historia 3 de punta a punta con MongoDB y RabbitMQ (CE-TRA-02 a CE-TRA-04)."""

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.comun.correlacion import id_correlacion_actual
from app.config import Configuracion
from app.integracion.rabbitmq import crear_sobre
from app.trabajos.esquemas import Trabajo
from app.trabajos.registro import DefinicionTipo
from tests.integration.conftest import (
    agregar_ruta_crear_trabajo,
    esperar_estado_final,
    esperar_rabbitmq,
)


class Contador:
    def __init__(self) -> None:
        self.ejecuciones = 0
        self.correlaciones: list[str | None] = []

    async def __call__(self, trabajo: Trabajo) -> dict[str, Any]:
        self.ejecuciones += 1
        self.correlaciones.append(id_correlacion_actual.get())
        logging.getLogger("app.prueba").info("procesando trabajo de prueba")
        await asyncio.sleep(0.2)
        return {"eco": trabajo.parametros}


@pytest.fixture
def contador() -> Contador:
    return Contador()


@pytest.fixture
def cliente_infra(
    crear_cliente: Callable[..., TestClient],
    configuracion_infra: Callable[..., Configuracion],
    contador: Contador,
) -> TestClient:
    def ajustar(app: FastAPI) -> None:
        app.state.registro_tipos.registrar(DefinicionTipo("PRUEBA", contador, timedelta(seconds=5)))
        agregar_ruta_crear_trabajo(app)

    cliente = crear_cliente(ajustar, configuracion_infra())
    esperar_rabbitmq(cliente)
    return cliente


def test_encolar_y_consultar_hasta_el_resultado(
    cliente_infra: TestClient, cabeceras_gerencia: dict[str, str], contador: Contador
) -> None:
    inicio = time.monotonic()
    creado = cliente_infra.post(
        "/api/ia/v1/prueba/trabajos/PRUEBA",
        json={"parametros": {"pregunta": "hola"}},
        headers={**cabeceras_gerencia, "X-Correlation-Id": "corr-flujo"},
    )

    assert creado.status_code == 202
    cuerpo = creado.json()
    assert cuerpo["estado"] == "EN_COLA"
    assert creado.headers["Location"] == f"/api/ia/v1/trabajos/{cuerpo['idTrabajo']}"

    en_curso = cliente_infra.get(creado.headers["Location"], headers=cabeceras_gerencia)
    assert en_curso.status_code == 200
    if en_curso.json()["estado"] in ("EN_COLA", "PROCESANDO"):
        assert en_curso.headers["Retry-After"] == "2"
        assert en_curso.json()["resultado"] is None

    final = esperar_estado_final(cliente_infra, cuerpo["idTrabajo"], cabeceras_gerencia)
    duracion = time.monotonic() - inicio

    assert final["estado"] == "COMPLETADO"
    assert final["resultado"] == {"eco": {"pregunta": "hola"}}
    assert final["error"] is None
    assert final["idCorrelacion"] == "corr-flujo"
    assert final["fechaInicio"] and final["fechaFin"]
    assert contador.correlaciones == ["corr-flujo"]
    assert duracion < 2.0, f"CE-TRA-02: tardó {duracion:.2f} s"


def test_la_creacion_responde_rapido(
    cliente_infra: TestClient, cabeceras_gerencia: dict[str, str]
) -> None:
    duraciones = []
    for _ in range(50):
        inicio = time.monotonic()
        respuesta = cliente_infra.post(
            "/api/ia/v1/prueba/trabajos/PRUEBA", json={}, headers=cabeceras_gerencia
        )
        duraciones.append(time.monotonic() - inicio)
        assert respuesta.status_code == 202

    p95 = sorted(duraciones)[int(len(duraciones) * 0.95) - 1]
    assert p95 < 0.5, f"CE-TRA-03: p95 de {p95:.3f} s"


def test_veinte_mensajes_del_mismo_trabajo_lo_ejecutan_una_vez(
    cliente_infra: TestClient, cabeceras_gerencia: dict[str, str], contador: Contador
) -> None:
    creado = cliente_infra.post(
        "/api/ia/v1/prueba/trabajos/PRUEBA", json={}, headers=cabeceras_gerencia
    ).json()
    conexion = cliente_infra.app.state.conexion_rabbitmq  # type: ignore[attr-defined]
    sobre = crear_sobre("ProcesarTrabajo", {"idTrabajo": creado["idTrabajo"]}, None)
    for _ in range(19):
        cliente_infra.portal.call(conexion.publicar, conexion.cola_trabajos, sobre)  # type: ignore[union-attr]

    esperar_estado_final(cliente_infra, creado["idTrabajo"], cabeceras_gerencia)
    time.sleep(0.5)  # da tiempo a que se consuman los duplicados

    assert contador.ejecuciones == 1


def test_otro_usuario_no_ve_el_trabajo(
    cliente_infra: TestClient, cabeceras_gerencia: dict[str, str]
) -> None:
    from tests.conftest import autorizacion, emitir_token

    creado = cliente_infra.post(
        "/api/ia/v1/prueba/trabajos/PRUEBA", json={}, headers=cabeceras_gerencia
    ).json()
    otro = autorizacion(emitir_token(["gerencia"], sub="luis"))

    respuesta = cliente_infra.get(f"/api/ia/v1/trabajos/{creado['idTrabajo']}", headers=otro)

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "TRABAJO_NO_ENCONTRADO"
