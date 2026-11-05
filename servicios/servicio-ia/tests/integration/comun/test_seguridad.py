"""spec-base.md, Historia 2, escenarios 1 a 4."""

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from tests.conftest import autorizacion, emitir_token

RUTA = "/api/ia/v1/prueba/gerencia"


def _sin_autenticar(respuesta_json: dict[str, object]) -> None:
    assert respuesta_json["codigo"] == "NO_AUTENTICADO"
    assert respuesta_json["mensaje"] == "Debe iniciar sesión para continuar."


def test_sin_token_responde_401(cliente: TestClient) -> None:
    respuesta = cliente.get(RUTA)

    assert respuesta.status_code == 401
    _sin_autenticar(respuesta.json())


def test_esquema_distinto_de_bearer_responde_401(cliente: TestClient) -> None:
    respuesta = cliente.get(RUTA, headers={"Authorization": "Basic YWJjOmRlZg=="})

    assert respuesta.status_code == 401


def test_token_mal_formado_responde_401(cliente: TestClient) -> None:
    respuesta = cliente.get(RUTA, headers=autorizacion("no-es-un-jwt"))

    assert respuesta.status_code == 401


@pytest.mark.parametrize(
    "opciones",
    [
        {"emisor": "http://otro-emisor/realms/agro"},
        {"audiencia": "servicio-gestion"},
        {"vence_en": -10},
        {"kid": "kid-desconocido"},
    ],
    ids=["emisor", "audiencia", "vencido", "kid"],
)
def test_token_invalido_responde_401(cliente: TestClient, opciones: dict[str, object]) -> None:
    token = emitir_token(["gerencia"], **opciones)  # type: ignore[arg-type]

    respuesta = cliente.get(RUTA, headers=autorizacion(token))

    assert respuesta.status_code == 401
    _sin_autenticar(respuesta.json())


def test_firma_con_otra_clave_responde_401(
    cliente: TestClient, otra_clave_privada: rsa.RSAPrivateKey
) -> None:
    token = emitir_token(["gerencia"], clave=otra_clave_privada)

    respuesta = cliente.get(RUTA, headers=autorizacion(token))

    assert respuesta.status_code == 401


def test_sin_el_rol_responde_403(cliente: TestClient) -> None:
    respuesta = cliente.get(RUTA, headers=autorizacion(emitir_token(["tecnico_campo"])))

    assert respuesta.status_code == 403
    assert respuesta.json()["codigo"] == "SIN_PERMISO"


@pytest.mark.parametrize("roles", [["gerencia"], ["administrador", "gerencia"]])
def test_con_el_rol_recibe_el_usuario(cliente: TestClient, roles: list[str]) -> None:
    token = emitir_token(roles, sub="abc", audiencia=["servicio-gestion", "servicio-ia"])

    respuesta = cliente.get(RUTA, headers=autorizacion(token))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"id": "abc", "nombre": "Ana Quispe", "roles": sorted(roles)}


def test_sin_name_usa_preferred_username(cliente: TestClient) -> None:
    token = emitir_token(["gerencia"], nombre=None)

    respuesta = cliente.get(RUTA, headers=autorizacion(token))

    assert respuesta.json()["nombre"] == "ana.quispe"


def test_ruta_inexistente_del_prefijo_responde_404_aunque_no_haya_token(
    cliente: TestClient,
) -> None:
    respuesta = cliente.get("/api/ia/v1/inexistente")

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "RECURSO_NO_ENCONTRADO"
