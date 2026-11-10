"""Versiones de modelos con MongoDB y S3 emulados (spec-prediccion.md, Historia 3)."""

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.comun.errores import ErrorAplicacion
from app.config import Configuracion
from app.integracion.repositorio_versiones import RepositorioVersionesMongo
from app.ml.entrenar import (
    Entrenado,
    armar_documento,
)
from app.modelos.cargador import CargadorModelos, EstadoCarga
from app.modelos.servicio import ServicioModelos
from tests.conftest import autorizacion, emitir_token
from tests.integration.conftest import almacen_s3, base_mongo_async, registrar_version

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "referencia_pequena.csv"
JUSTIFICACION = "Se agregan campañas reales del sistema al entrenamiento."


def _servicio(proyecto: str, bucket: str) -> tuple[ServicioModelos, CargadorModelos]:
    cliente = base_mongo_async(proyecto)
    cargador = CargadorModelos(RepositorioVersionesMongo(cliente), almacen_s3(bucket))
    cargador.registrar("rendimiento")
    return ServicioModelos(RepositorioVersionesMongo(cliente), cargador), cargador


async def test_versiones_incrementales_y_publicacion_con_regla_de_metricas(
    base_mongo: str, prefijo_s3: str, entrenados: dict[str, Entrenado]
) -> None:
    v1 = await registrar_version(
        base_mongo, prefijo_s3, "rendimiento", entrenados["rendimiento"], 600
    )
    v2 = await registrar_version(
        base_mongo, prefijo_s3, "rendimiento", entrenados["rendimiento"], 700
    )
    assert (v1, v2) == (1, 2)
    servicio, cargador = _servicio(base_mongo, prefijo_s3)

    publicada = await servicio.publicar("rendimiento", 1, None)
    assert publicada.estado.value == "VIGENTE"
    assert publicada.fecha_publicacion is not None
    await cargador.esperar_pendientes()  # carga en segundo plano, sin esperar el ciclo
    assert cargador.estado("rendimiento") is EstadoCarga.CARGADO
    assert cargador.obtener("rendimiento").version.version == 1

    with pytest.raises(ErrorAplicacion) as error:
        await servicio.publicar("rendimiento", 2, "corta")
    assert (error.value.estado_http, error.value.codigo) == (422, "METRICAS_INFERIORES")

    publicada = await servicio.publicar("rendimiento", 2, JUSTIFICACION)
    assert publicada.justificacion == JUSTIFICACION
    estados = {v.version: v.estado.value for v in await servicio.listar("rendimiento")}
    assert estados == {1: "RETIRADA", 2: "VIGENTE"}
    await cargador.esperar_pendientes()
    assert cargador.obtener("rendimiento").version.version == 2


async def test_no_se_publica_una_vigente_ni_una_inexistente(
    base_mongo: str, prefijo_s3: str, entrenados: dict[str, Entrenado]
) -> None:
    await registrar_version(base_mongo, prefijo_s3, "rendimiento", entrenados["rendimiento"])
    servicio, _ = _servicio(base_mongo, prefijo_s3)
    await servicio.publicar("rendimiento", 1, None)

    with pytest.raises(ErrorAplicacion) as vigente:
        await servicio.publicar("rendimiento", 1, None)
    with pytest.raises(ErrorAplicacion) as inexistente:
        await servicio.publicar("rendimiento", 9, None)

    assert (vigente.value.estado_http, vigente.value.codigo) == (409, "VERSION_NO_PUBLICABLE")
    assert (inexistente.value.estado_http, inexistente.value.codigo) == (
        404,
        "VERSION_MODELO_NO_ENCONTRADA",
    )


async def test_publicaciones_simultaneas_dejan_una_sola_vigente(
    base_mongo: str, prefijo_s3: str, entrenados: dict[str, Entrenado]
) -> None:
    for _ in range(3):
        await registrar_version(
            base_mongo, prefijo_s3, "rendimiento", entrenados["rendimiento"], 600
        )
    servicios = [_servicio(base_mongo, prefijo_s3)[0] for _ in range(3)]

    await asyncio.gather(
        *(s.publicar("rendimiento", v, None) for s, v in zip(servicios, (1, 2, 3), strict=True)),
        return_exceptions=True,
    )

    estados = [v.estado.value for v in await servicios[0].listar("rendimiento")]
    assert estados.count("VIGENTE") == 1


async def test_cargador_sin_version_o_con_artefacto_faltante(
    base_mongo: str, prefijo_s3: str, entrenados: dict[str, Entrenado]
) -> None:
    servicio, cargador = _servicio(base_mongo, prefijo_s3)
    await cargador.revisar()
    assert cargador.estado("rendimiento") is EstadoCarga.SIN_PUBLICAR
    with pytest.raises(ErrorAplicacion) as error:
        cargador.obtener("rendimiento")
    assert error.value.codigo == "MODELO_NO_DISPONIBLE"

    repositorio = RepositorioVersionesMongo(base_mongo_async(base_mongo))
    documento = armar_documento(
        "rendimiento",
        entrenados["rendimiento"],
        [],
        "modelos/rendimiento/sin-archivos",
        "0" * 64,
        7,
        datetime.now(UTC),
    )
    await repositorio.registrar_candidata(documento)
    await servicio.publicar("rendimiento", 1, None)
    await cargador.esperar_pendientes()  # la publicación carga en segundo plano
    assert cargador.estado("rendimiento") is EstadoCarga.ERROR


def _esperar_carga(cliente: TestClient, nombre: str) -> None:
    cargador: CargadorModelos = cliente.app.state.cargador_modelos  # type: ignore[attr-defined]
    fin = time.monotonic() + 10
    while time.monotonic() < fin and cargador.estado(nombre) is not EstadoCarga.CARGADO:
        cliente.portal.call(cargador.revisar)  # type: ignore[union-attr]
        time.sleep(0.1)
    assert cargador.estado(nombre) is EstadoCarga.CARGADO


def test_endpoints_de_modelos_con_permisos(
    crear_cliente: Callable[..., TestClient],
    configuracion_infra: Callable[..., Configuracion],
    base_mongo: str,
    prefijo_s3: str,
    entrenados: dict[str, Entrenado],
) -> None:
    asyncio.run(registrar_version(base_mongo, prefijo_s3, "patrones", entrenados["patrones"]))
    cliente = crear_cliente(configuracion=configuracion_infra(trabajos_consumidor_activo=False))
    admin = autorizacion(emitir_token(["administrador"]))
    gerencia = autorizacion(emitir_token(["gerencia"]))
    tecnico = autorizacion(emitir_token(["tecnico_campo"]))

    listado = cliente.get("/api/ia/v1/modelos?nombre=patrones", headers=gerencia)
    assert listado.status_code == 200
    (version,) = listado.json()
    assert version["estado"] == "CANDIDATA"
    assert version["metricaPrincipal"]["nombre"] == "silueta"
    assert version["filasPorOrigen"] == {"ERS": 60}
    assert cliente.get("/api/ia/v1/modelos", headers=tecnico).status_code == 403

    ruta = "/api/ia/v1/modelos/patrones/versiones/1/publicacion"
    assert cliente.post(ruta, headers=gerencia).status_code == 403
    publicada = cliente.post(ruta, json={}, headers=admin)
    assert publicada.status_code == 200
    assert publicada.json()["estado"] == "VIGENTE"
    _esperar_carga(cliente, "patrones")
    salud: dict[str, Any] = cliente.get("/salud/readiness").json()
    assert salud["informativos"]["modelo_patrones"] == "UP"
    assert salud["informativos"]["modelo_rendimiento"] == "DOWN"  # sin publicar: no es crítico
