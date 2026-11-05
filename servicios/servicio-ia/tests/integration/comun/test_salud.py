"""spec-base.md, Historia 1."""

import asyncio
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient


async def _sana() -> None:
    return None


async def _caida() -> None:
    raise ConnectionError("sin conexión")


async def _lenta() -> None:
    await asyncio.sleep(5)


def test_liveness_sin_token(cliente: TestClient) -> None:
    respuesta = cliente.get("/salud/liveness")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "UP"}


def test_readiness_sin_comprobaciones(cliente: TestClient) -> None:
    for ruta in ("/salud/readiness", "/salud"):
        respuesta = cliente.get(ruta)
        assert respuesta.status_code == 200
        assert respuesta.json() == {"estado": "UP", "componentes": {}, "informativos": {}}


def test_critica_caida_responde_503(crear_cliente: Callable[..., TestClient]) -> None:
    def ajustar(app: FastAPI) -> None:
        app.state.registro_salud.registrar("firestore", _sana, critica=True)
        app.state.registro_salud.registrar("rabbitmq", _caida, critica=True)

    respuesta = crear_cliente(ajustar).get("/salud/readiness")

    assert respuesta.status_code == 503
    assert respuesta.json() == {
        "estado": "DOWN",
        "componentes": {"firestore": "UP", "rabbitmq": "DOWN"},
        "informativos": {},
    }


def test_informativa_caida_o_lenta_no_cambia_el_estado(
    crear_cliente: Callable[..., TestClient],
) -> None:
    def ajustar(app: FastAPI) -> None:
        app.state.registro_salud.registrar("firestore", _sana, critica=True)
        app.state.registro_salud.registrar("ollama", _lenta, critica=False)

    respuesta = crear_cliente(ajustar).get("/salud")

    assert respuesta.status_code == 200
    assert respuesta.json()["informativos"] == {"ollama": "DOWN"}
