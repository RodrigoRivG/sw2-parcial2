import json

import pytest

from app.main import crear_app


def test_sin_configuracion_el_proceso_termina_con_el_nombre_de_las_variables(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for nombre in (
        "KEYCLOAK_ISSUER",
        "KEYCLOAK_JWKS_URI",
        "KEYCLOAK_AUDIENCE",
        "KEYCLOAK_TOKEN_URL",
        "KEYCLOAK_CLIENT_ID",
        "KEYCLOAK_CLIENT_SECRET",
        "API_GATEWAY_URL",
        "GOOGLE_CLOUD_PROJECT",
        "RABBITMQ_URL",
    ):
        monkeypatch.delenv(nombre, raising=False)

    with pytest.raises(SystemExit) as salida:
        crear_app()

    assert salida.value.code == 1
    registro = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert registro["nivel"] == "ERROR"
    assert "API_GATEWAY_URL" in registro["variables"]
