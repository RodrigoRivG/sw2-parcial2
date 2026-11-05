"""spec-base.md, Historia 3, escenarios 4 a 6."""

import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from tests.conftest import autorizacion, emitir_token


def test_devuelve_el_id_recibido_en_respuestas_correctas_y_de_error(cliente: TestClient) -> None:
    correcta = cliente.get("/salud/liveness", headers={"X-Correlation-Id": "abc-123"})
    sin_token = cliente.get("/api/ia/v1/prueba/gerencia", headers={"X-Correlation-Id": "abc-124"})
    sin_rol = cliente.get(
        "/api/ia/v1/prueba/gerencia",
        headers={**autorizacion(emitir_token([])), "X-Correlation-Id": "abc-125"},
    )

    assert correcta.headers["X-Correlation-Id"] == "abc-123"
    assert sin_token.headers["X-Correlation-Id"] == "abc-124"
    assert sin_token.json()["idCorrelacion"] == "abc-124"
    assert sin_rol.headers["X-Correlation-Id"] == "abc-125"
    assert sin_rol.json()["idCorrelacion"] == "abc-125"


@pytest.mark.parametrize("recibido", [None, "con espacios", "a" * 65])
def test_genera_un_uuid_si_falta_o_es_invalido(cliente: TestClient, recibido: str | None) -> None:
    cabeceras = {"X-Correlation-Id": recibido} if recibido else {}

    respuesta = cliente.get("/salud/liveness", headers=cabeceras)

    uuid.UUID(respuesta.headers["X-Correlation-Id"])


def test_log_de_acceso_con_sub_y_sin_token(
    cliente: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    token = emitir_token(["gerencia"], sub="sub-42")

    with caplog.at_level(logging.INFO, logger="app.acceso"):
        cliente.get(
            "/api/ia/v1/prueba/gerencia?x=1",
            headers={**autorizacion(token), "X-Correlation-Id": "id-acceso"},
        )

    registro = next(r for r in caplog.records if r.name == "app.acceso")
    assert registro.getMessage() == "solicitud atendida"
    assert registro.__dict__["metodo"] == "GET"
    assert registro.__dict__["ruta"] == "/api/ia/v1/prueba/gerencia"
    assert registro.__dict__["estado"] == 200
    assert registro.__dict__["sub"] == "sub-42"
    assert isinstance(registro.__dict__["duracionMs"], float)
    assert token not in caplog.text
