"""spec-base.md RQ-BASE-10 y README D-14."""

from fastapi.testclient import TestClient

ERRORES_MINIMOS = {"400", "401", "403", "500"}


def test_documentacion_sin_token(cliente: TestClient) -> None:
    assert cliente.get("/openapi.json").status_code == 200
    assert cliente.get("/docs").status_code == 200


def test_toda_ruta_del_prefijo_documenta_sus_errores(cliente: TestClient) -> None:
    contrato = cliente.get("/openapi.json").json()
    esquema_error = "#/components/schemas/RespuestaError"

    rutas = {r: o for r, o in contrato["paths"].items() if r.startswith("/api/ia/v1/")}
    assert rutas, "No hay rutas del prefijo para revisar"
    for ruta, operaciones in rutas.items():
        for metodo, operacion in operaciones.items():
            respuestas = operacion["responses"]
            faltantes = ERRORES_MINIMOS - respuestas.keys()
            assert not faltantes, f"{metodo.upper()} {ruta} no documenta {faltantes}"
            for codigo in ERRORES_MINIMOS:
                contenido = respuestas[codigo]["content"]["application/json"]["schema"]
                assert contenido["$ref"] == esquema_error, f"{metodo.upper()} {ruta} {codigo}"
