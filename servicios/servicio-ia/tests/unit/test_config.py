import pytest

from app.config import ConfiguracionInvalida, cargar_configuracion

VARIABLES = {
    "KEYCLOAK_ISSUER": "http://localhost:8180/realms/agro",
    "KEYCLOAK_JWKS_URI": "http://keycloak:8080/realms/agro/protocol/openid-connect/certs",
    "KEYCLOAK_AUDIENCE": "servicio-ia",
    "KEYCLOAK_TOKEN_URL": "http://keycloak:8080/realms/agro/protocol/openid-connect/token",
    "KEYCLOAK_CLIENT_ID": "servicio-ia",
    "KEYCLOAK_CLIENT_SECRET": "secreto-de-prueba",
    "API_GATEWAY_URL": "http://api-gateway:8080/",
    "GOOGLE_CLOUD_PROJECT": "sw2-local",
    "RABBITMQ_URL": "amqp://sw2:clave@rabbitmq:5672",
}


@pytest.fixture
def entorno(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for nombre, valor in VARIABLES.items():
        monkeypatch.setenv(nombre, valor)
    return monkeypatch


def test_lee_las_variables_y_quita_la_barra_final_del_gateway(entorno: pytest.MonkeyPatch) -> None:
    configuracion = cargar_configuracion()

    assert configuracion.keycloak_audience == "servicio-ia"
    assert configuracion.api_gateway_url == "http://api-gateway:8080"
    assert configuracion.gateway_tiempo_limite_segundos == 5.0
    assert configuracion.keycloak_client_secret.get_secret_value() == "secreto-de-prueba"


@pytest.mark.parametrize("nombre", ["KEYCLOAK_AUDIENCE", "API_GATEWAY_URL"])
def test_falta_una_variable_obligatoria(entorno: pytest.MonkeyPatch, nombre: str) -> None:
    entorno.delenv(nombre)

    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_configuracion()

    assert error.value.variables == [nombre]


def test_secreto_vacio_cuenta_como_faltante_y_no_se_muestra(entorno: pytest.MonkeyPatch) -> None:
    entorno.setenv("KEYCLOAK_CLIENT_SECRET", "  ")
    entorno.setenv("KEYCLOAK_ISSUER", "")

    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_configuracion()

    assert error.value.variables == ["KEYCLOAK_CLIENT_SECRET", "KEYCLOAK_ISSUER"]
    assert "secreto-de-prueba" not in str(error.value)
