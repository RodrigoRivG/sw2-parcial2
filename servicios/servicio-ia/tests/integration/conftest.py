"""Infraestructura real para los tests de integración (spec-trabajos.md 2.13).

Cada test usa un proyecto de MongoDB, un bucket y colas propios, que se borran al terminar,
para no chocar con el servicio que esté corriendo en Docker Compose.
"""

import asyncio
import os
import time
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aio_pika
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.comun.errores import respuestas_error
from app.comun.esquemas import ModeloEntrada
from app.comun.seguridad import UsuarioAutenticado, router_protegido, usuario_actual
from app.config import Configuracion
from app.integracion.almacen_archivos import AlmacenS3
from app.integracion.repositorio_versiones import RepositorioVersionesMongo
from app.ml.entrenar import (
    Entrenado,
    a_bytes_joblib,
    armar_documento,
    entrenar_patrones,
    entrenar_rendimiento,
    leer_referencia,
)
from app.trabajos.servicio import ServicioTrabajos, respuesta_creado, servicio_trabajos
from tests.conftest import RABBITMQ_URL, autorizacion, configuracion_de_prueba, emitir_token


def cliente_mongo() -> Any:
    from pymongo import MongoClient

    return MongoClient(os.environ["MONGODB_URI"], tz_aware=True, timeoutMS=5000)


def base_mongo_async(nombre: str) -> Any:
    from app.integracion.mongodb import crear_cliente_mongo

    return crear_cliente_mongo(os.environ["MONGODB_URI"])[nombre]


def cliente_s3() -> Any:
    import boto3

    return boto3.client("s3", endpoint_url=os.environ["AWS_ENDPOINT"])


def almacen_s3(prefijo: str) -> AlmacenS3:
    return AlmacenS3(os.environ["AWS_BUCKET"], prefijo, os.environ["AWS_ENDPOINT"])


@pytest.fixture
def base_mongo() -> Iterator[str]:
    nombre = f"pruebas-{uuid.uuid4().hex[:12]}"
    yield nombre
    with cliente_mongo() as cliente:
        cliente.drop_database(nombre)


async def _borrar_colas(nombres: list[str]) -> None:
    conexion = await aio_pika.connect(RABBITMQ_URL, timeout=5)
    async with conexion:
        canal = await conexion.channel()
        for nombre in nombres:
            await canal.queue_delete(nombre)


@pytest.fixture
def cola_trabajos() -> Iterator[str]:
    cola = f"pruebas-{uuid.uuid4().hex[:8]}.servicio-ia.trabajos"
    yield cola
    asyncio.run(_borrar_colas([cola, f"{cola}.dlq"]))


@pytest.fixture
def prefijo_s3() -> Iterator[str]:
    prefijo = f"pruebas-{uuid.uuid4().hex[:12]}/"
    cliente = cliente_s3()
    bucket = os.environ["AWS_BUCKET"]
    # Solo LocalStack: no se crean ni vacían buckets reales en los tests.
    yield prefijo
    for pagina in cliente.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefijo):
        for objeto in pagina.get("Contents", []):
            cliente.delete_object(Bucket=bucket, Key=objeto["Key"])
    cliente.close()


@pytest.fixture
def configuracion_infra(
    base_mongo: str, cola_trabajos: str, prefijo_s3: str
) -> Callable[..., Configuracion]:
    def crear(**cambios: Any) -> Configuracion:
        valores: dict[str, Any] = {
            "mongodb_uri": SecretStr(os.environ["MONGODB_URI"]),
            "mongodb_base": base_mongo,
            "aws_endpoint": os.environ["AWS_ENDPOINT"],
            "s3_prefijo": prefijo_s3,
            "rabbitmq_url": SecretStr(RABBITMQ_URL),
            "trabajos_cola": cola_trabajos,
            "trabajos_consumidor_activo": True,
            "aws_bucket": os.environ["AWS_BUCKET"],
        }
        valores.update(cambios)
        return configuracion_de_prueba(**valores)

    return crear


class CuerpoTrabajoPrueba(ModeloEntrada):
    parametros: dict[str, Any] = {}


def agregar_ruta_crear_trabajo(app: FastAPI) -> None:
    """`POST /api/ia/v1/prueba/trabajos/{tipo}`: crea un trabajo de ese tipo (solo en tests)."""
    router = router_protegido(tags=["prueba"])

    @router.post("/prueba/trabajos/{tipo}", responses=respuestas_error(400, 401, 403, 500, 503))
    async def crear(
        tipo: str,
        cuerpo: CuerpoTrabajoPrueba,
        usuario: UsuarioAutenticado = Depends(usuario_actual),
        servicio: ServicioTrabajos = Depends(servicio_trabajos),
    ) -> Any:
        trabajo = await servicio.crear(tipo, cuerpo.parametros, usuario)
        return respuesta_creado(trabajo)

    app.include_router(router)


def esperar_estado_final(
    cliente: TestClient, id_trabajo: str, cabeceras: dict[str, str], tiempo_limite: float = 10.0
) -> dict[str, Any]:
    fin = time.monotonic() + tiempo_limite
    while time.monotonic() < fin:
        respuesta = cliente.get(f"/api/ia/v1/trabajos/{id_trabajo}", headers=cabeceras)
        cuerpo: dict[str, Any] = respuesta.json()
        if cuerpo.get("estado") in ("COMPLETADO", "FALLIDO"):
            return cuerpo
        time.sleep(0.05)
    raise AssertionError(f"El trabajo {id_trabajo} no terminó en {tiempo_limite} s")


def esperar_rabbitmq(cliente: TestClient, tiempo_limite: float = 15.0) -> None:
    """Espera a que la conexión de fondo a RabbitMQ esté lista."""
    fin = time.monotonic() + tiempo_limite
    while time.monotonic() < fin:
        if cliente.get("/salud/readiness").json()["componentes"].get("rabbitmq") == "UP":
            return
        time.sleep(0.1)
    raise AssertionError("RabbitMQ no quedó disponible")


@pytest.fixture
def cabeceras_gerencia() -> dict[str, str]:
    return autorizacion(emitir_token(["gerencia"], sub="ana"))


# --- Modelos (spec-prediccion.md) -----------------------------------------------------------

FIXTURE_REFERENCIA = Path(__file__).resolve().parents[1] / "fixtures" / "referencia_pequena.csv"


@pytest.fixture(scope="module")
def entrenados() -> dict[str, Entrenado]:
    filas = leer_referencia(FIXTURE_REFERENCIA)
    return {"rendimiento": entrenar_rendimiento(filas, 7), "patrones": entrenar_patrones(filas, 7)}


async def registrar_version(
    proyecto: str,
    bucket: str,
    nombre: str,
    entrenado: Entrenado,
    valor_metrica: float | None = None,
) -> int:
    """Sube los artefactos y registra una CANDIDATA, como `python -m app.ml.entrenar`."""
    filas = leer_referencia(FIXTURE_REFERENCIA)
    almacen = almacen_s3(bucket)
    ruta = f"modelos/{nombre}/{time.time_ns()}"
    documento = armar_documento(nombre, entrenado, filas, ruta, "0" * 64, 7, datetime.now(UTC))
    if valor_metrica is not None:
        documento["metricaPrincipal"] = {**documento["metricaPrincipal"], "valor": valor_metrica}
    await almacen.subir(
        f"{ruta}/modelo.joblib", a_bytes_joblib(entrenado.artefacto), "application/octet-stream"
    )
    repositorio = RepositorioVersionesMongo(base_mongo_async(proyecto))
    return await repositorio.registrar_candidata(documento)
