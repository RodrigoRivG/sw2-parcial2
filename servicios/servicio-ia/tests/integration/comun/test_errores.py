"""spec-base.md, Historia 3, escenarios 1 a 3, e Historia 4, escenario 7."""

import logging

import pytest
from fastapi.testclient import TestClient

from tests.conftest import autorizacion, emitir_token

RUTA_VALIDACION = "/api/ia/v1/prueba/validacion"


@pytest.fixture
def cabeceras() -> dict[str, str]:
    return autorizacion(emitir_token(["gerencia"]))


def test_cuerpo_valido(cliente: TestClient, cabeceras: dict[str, str]) -> None:
    respuesta = cliente.post(
        RUTA_VALIDACION, json={"nombre": "x", "montoTotal": "820.50"}, headers=cabeceras
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"montoTotal": "820.50"}


def test_campo_faltante_y_numero_json_en_decimal(
    cliente: TestClient, cabeceras: dict[str, str]
) -> None:
    respuesta = cliente.post(RUTA_VALIDACION, json={"montoTotal": 820.5}, headers=cabeceras)

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "DATOS_INVALIDOS"
    assert cuerpo["mensaje"] == "Los datos enviados no son válidos."
    detalles = {d["campo"]: d["mensaje"] for d in cuerpo["detalles"]}
    assert detalles["nombre"] == "Campo obligatorio."
    assert detalles["montoTotal"] == 'Debe enviarse como texto decimal, por ejemplo "820.50".'
    assert cuerpo["idCorrelacion"]


def test_campo_desconocido_y_tipo_incorrecto(
    cliente: TestClient, cabeceras: dict[str, str]
) -> None:
    respuesta = cliente.post(
        RUTA_VALIDACION,
        json={"nombre": 5, "montoTotal": "1.00", "otroCampo": True},
        headers=cabeceras,
    )

    detalles = {d["campo"]: d["mensaje"] for d in respuesta.json()["detalles"]}
    assert detalles == {"nombre": "Debe ser texto.", "otroCampo": "Campo no permitido."}


def test_json_mal_formado(cliente: TestClient, cabeceras: dict[str, str]) -> None:
    respuesta = cliente.post(
        RUTA_VALIDACION,
        content=b'{"nombre": ',
        headers={**cabeceras, "Content-Type": "application/json"},
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["detalles"][0]["campo"] == "cuerpo"


def test_ruta_inexistente_y_metodo_no_permitido(cliente: TestClient) -> None:
    assert cliente.get("/no-existe").json()["codigo"] == "RECURSO_NO_ENCONTRADO"

    respuesta = cliente.delete("/salud/liveness")
    assert respuesta.status_code == 405
    assert respuesta.json()["codigo"] == "METODO_NO_PERMITIDO"


def test_error_inesperado_responde_500_sin_detalles_y_lo_registra(
    cliente: TestClient, cabeceras: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.errores"):
        respuesta = cliente.get(
            "/api/ia/v1/prueba/error-interno", headers={**cabeceras, "X-Correlation-Id": "id-500"}
        )

    assert respuesta.status_code == 500
    assert respuesta.json() == {
        "codigo": "ERROR_INTERNO",
        "mensaje": "Ocurrió un error inesperado.",
        "detalles": [],
        "idCorrelacion": "id-500",
    }
    assert respuesta.headers["X-Correlation-Id"] == "id-500"
    assert "detalle que no debe salir" not in respuesta.text
    assert any(r.exc_info for r in caplog.records)


def test_servicio_remoto_no_disponible_sin_manejar_responde_503(
    cliente: TestClient, cabeceras: dict[str, str]
) -> None:
    respuesta = cliente.get("/api/ia/v1/prueba/error-remoto/NO_DISPONIBLE", headers=cabeceras)

    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "DEPENDENCIA_NO_DISPONIBLE"


@pytest.mark.parametrize("tipo", ["NO_ENCONTRADO", "RECHAZADO"])
def test_otros_errores_remotos_sin_manejar_responden_500(
    cliente: TestClient, cabeceras: dict[str, str], tipo: str
) -> None:
    respuesta = cliente.get(f"/api/ia/v1/prueba/error-remoto/{tipo}", headers=cabeceras)

    assert respuesta.status_code == 500
    assert respuesta.json()["codigo"] == "ERROR_INTERNO"
