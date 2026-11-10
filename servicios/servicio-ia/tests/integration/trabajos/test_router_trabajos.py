"""GET /api/ia/v1/trabajos/{id} con trabajos guardados en el emulador (spec-trabajos.md 2.11)."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Configuracion
from app.trabajos.esquemas import ErrorTrabajo, Trabajo
from app.trabajos.estados import EstadoTrabajo
from tests.integration.conftest import cliente_mongo

AHORA = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


@pytest.fixture
def cliente(
    crear_cliente: Callable[..., TestClient], configuracion_infra: Callable[..., Configuracion]
) -> TestClient:
    return crear_cliente(configuracion=configuracion_infra(trabajos_consumidor_activo=False))


@pytest.fixture
def guardar(base_mongo: str) -> Callable[..., str]:
    coleccion = cliente_mongo()[base_mongo]["trabajos"]

    def guardar_trabajo(estado: str, **cambios: Any) -> str:
        trabajo = Trabajo(
            id=str(uuid.uuid4()),
            tipo="REPORTE",
            estado=EstadoTrabajo(estado),
            id_solicitante="ana",
            id_correlacion="corr",
            parametros={"secreto": "no se devuelve"},
            fecha_creacion=AHORA,
            **cambios,
        )
        coleccion.insert_one({**trabajo.a_documento(), "_id": trabajo.id})
        return trabajo.id

    return guardar_trabajo


@pytest.mark.parametrize("estado", ["EN_COLA", "PROCESANDO"])
def test_en_curso_con_retry_after_y_sin_resultado(
    cliente: TestClient,
    guardar: Callable[..., str],
    cabeceras_gerencia: dict[str, str],
    estado: str,
) -> None:
    id_trabajo = guardar(estado, resultado={"x": 1})

    respuesta = cliente.get(f"/api/ia/v1/trabajos/{id_trabajo}", headers=cabeceras_gerencia)

    assert respuesta.status_code == 200
    assert respuesta.headers["Retry-After"] == "2"
    assert respuesta.json()["resultado"] is None
    assert respuesta.json()["estado"] == estado


def test_completado_devuelve_el_resultado_y_nada_interno(
    cliente: TestClient, guardar: Callable[..., str], cabeceras_gerencia: dict[str, str]
) -> None:
    id_trabajo = guardar("COMPLETADO", resultado={"x": 1}, fecha_inicio=AHORA, fecha_fin=AHORA)

    respuesta = cliente.get(f"/api/ia/v1/trabajos/{id_trabajo}", headers=cabeceras_gerencia)

    assert "Retry-After" not in respuesta.headers
    assert respuesta.json() == {
        "idTrabajo": id_trabajo,
        "tipo": "REPORTE",
        "estado": "COMPLETADO",
        "fechaCreacion": "2026-11-04T12:00:00Z",
        "fechaInicio": "2026-11-04T12:00:00Z",
        "fechaFin": "2026-11-04T12:00:00Z",
        "idCorrelacion": "corr",
        "resultado": {"x": 1},
        "error": None,
    }


def test_fallido_devuelve_el_error(
    cliente: TestClient, guardar: Callable[..., str], cabeceras_gerencia: dict[str, str]
) -> None:
    error = ErrorTrabajo(codigo="TIEMPO_AGOTADO", mensaje="El trabajo superó el tiempo máximo.")
    id_trabajo = guardar("FALLIDO", error=error)

    cuerpo = cliente.get(f"/api/ia/v1/trabajos/{id_trabajo}", headers=cabeceras_gerencia).json()

    assert cuerpo["error"] == {
        "codigo": "TIEMPO_AGOTADO",
        "mensaje": "El trabajo superó el tiempo máximo.",
    }
    assert cuerpo["resultado"] is None


def test_sin_token_401_y_ajeno_404(cliente: TestClient, guardar: Callable[..., str]) -> None:
    from tests.conftest import autorizacion, emitir_token

    id_trabajo = guardar("COMPLETADO")

    assert cliente.get(f"/api/ia/v1/trabajos/{id_trabajo}").status_code == 401
    ajeno = cliente.get(
        f"/api/ia/v1/trabajos/{id_trabajo}", headers=autorizacion(emitir_token([], sub="otro"))
    )
    assert ajeno.status_code == 404
    assert ajeno.json()["mensaje"] == "El trabajo solicitado no existe."


def test_mongodb_inalcanzable_responde_503(
    crear_cliente: Callable[..., TestClient],
    configuracion_infra: Callable[..., Configuracion],
    cabeceras_gerencia: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MONGODB_URI", "mongodb://invalido.prueba:27017/?serverSelectionTimeoutMS=100"
    )
    cliente = crear_cliente(configuracion=configuracion_infra(trabajos_consumidor_activo=False))

    respuesta = cliente.get(f"/api/ia/v1/trabajos/{uuid.uuid4()}", headers=cabeceras_gerencia)

    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "DEPENDENCIA_NO_DISPONIBLE"
