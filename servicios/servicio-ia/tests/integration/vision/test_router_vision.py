"""Endpoints de visión con un modelo diminuto publicado en los emuladores (spec-vision.md 2.8)."""

import asyncio
import io
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Configuracion
from app.integracion.repositorio_versiones import RepositorioVersionesMongo
from app.ml.clasificador import (
    Configuracion as ConfigEntrenamiento,
)
from app.ml.clasificador import (
    armar_documento,
    artefactos,
    cargar_particiones,
    entrenar,
    leer_manifiesto,
    recorte_central,
)
from app.modelos.cargador import CargadorModelos, EstadoCarga
from app.vision.etiquetas import CATEGORIAS
from tests.conftest import autorizacion, emitir_token
from tests.integration.conftest import (
    almacen_s3,
    base_mongo_async,
    cliente_mongo,
    cliente_s3,
    esperar_estado_final,
    esperar_rabbitmq,
)
from tests.unit.vision.test_video import crear_video

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "imagenes"
TECNICO = autorizacion(emitir_token(["tecnico_campo"], sub="tec"))
GERENCIA = autorizacion(emitir_token(["gerencia"]))


@pytest.fixture(scope="module")
def diminuto() -> tuple[dict[str, bytes], dict[str, Any]]:
    manifiesto = leer_manifiesto(FIXTURES / "manifiesto.csv")
    particiones = cargar_particiones(manifiesto, FIXTURES)
    config = ConfigEntrenamiento(
        arquitectura="small", pesos=None, epocas_fase1=1, epocas_fase2=0, semilla=3
    )
    modelo, historial = entrenar(particiones, config)
    archivos, exportaciones = artefactos(modelo, recorte_central(particiones["prueba"].imagenes))
    metricas = {"f1Macro": 0.1, "exactitud": 0.1}
    documento = armar_documento(
        metricas,
        historial,
        exportaciones,
        manifiesto,
        {"ruta": "datasets/imagenes/x.tar", "sha256": "0" * 64},
        "",
        config,
        datetime.now(UTC),
    )
    documento["adicionales"]["umbral"] = 0.0  # el modelo diminuto no llega al umbral real
    return archivos, documento


async def _publicar(
    proyecto: str, bucket: str, archivos: dict[str, bytes], documento: dict[str, Any]
) -> None:
    almacen = almacen_s3(bucket)
    ruta = f"modelos/clasificador/{time.time_ns()}"
    for nombre, datos in archivos.items():
        await almacen.subir(f"{ruta}/{nombre}", datos, "application/octet-stream")
    repositorio = RepositorioVersionesMongo(base_mongo_async(proyecto))
    version = await repositorio.registrar_candidata({**documento, "rutaArtefactos": ruta})
    await repositorio.publicar("clasificador", version, lambda c, v: {"justificacion": None})


@pytest.fixture
def cliente(
    crear_cliente: Callable[..., TestClient],
    configuracion_infra: Callable[..., Configuracion],
    base_mongo: str,
    prefijo_s3: str,
    diminuto: tuple[dict[str, bytes], dict[str, Any]],
) -> TestClient:
    asyncio.run(_publicar(base_mongo, prefijo_s3, *diminuto))
    cliente = crear_cliente(configuracion=configuracion_infra(vision_tamanio_maximo_video_mb=5.0))
    cargador: CargadorModelos = cliente.app.state.cargador_modelos  # type: ignore[attr-defined]
    cliente.portal.call(cargador.revisar)  # type: ignore[union-attr]
    assert cargador.estado("clasificador") is EstadoCarga.CARGADO
    return cliente


def _jpeg(ancho: int = 640, alto: int = 480, ruido: bool = False) -> bytes:
    if ruido:
        datos = np.random.default_rng(1).integers(0, 255, (alto, ancho, 3), dtype=np.uint8)
        imagen = Image.fromarray(datos)
    else:
        imagen = Image.open(next(FIXTURES.glob("SOYA_ROYA/*.jpg")))
    salida = io.BytesIO()
    imagen.save(salida, format="JPEG", quality=95)
    return salida.getvalue()


def test_clasificar_foto(cliente: TestClient, base_mongo: str) -> None:
    respuesta = cliente.post(
        "/api/ia/v1/clasificaciones",
        files={"imagen": ("hoja.jpg", _jpeg(), "image/jpeg")},
        headers=TECNICO,
    )

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["categoria"] in CATEGORIAS
    assert len(cuerpo["alternativas"]) == 2
    assert cuerpo["clasificacion"] == {
        "categoria": cuerpo["categoria"],
        "confianza": cuerpo["confianza"],
        "versionModelo": "clasificador-1",
        "origen": "SERVIDOR",
    }
    assert len(cuerpo["confianza"]) == 6  # "0.xxxx"
    assert cuerpo["orientativo"] is True
    (guardado,) = [d for d in cliente_mongo()[base_mongo]["clasificaciones"].find({}, {"_id": 0})]
    assert guardado["idSolicitante"] == "tec"
    assert len(guardado["sha256Imagen"]) == 64
    assert "imagen" not in guardado


def test_errores_de_clasificacion(cliente: TestClient) -> None:
    invalida = cliente.post(
        "/api/ia/v1/clasificaciones",
        files={"imagen": ("x.jpg", b"texto", "image/jpeg")},
        headers=TECNICO,
    )
    sin_archivo = cliente.post("/api/ia/v1/clasificaciones", headers=TECNICO)
    gerencia = cliente.post(
        "/api/ia/v1/clasificaciones",
        files={"imagen": ("h.jpg", _jpeg(), "image/jpeg")},
        headers=GERENCIA,
    )

    assert (invalida.status_code, invalida.json()["codigo"]) == (400, "IMAGEN_INVALIDA")
    assert (sin_archivo.status_code, sin_archivo.json()["codigo"]) == (400, "DATOS_INVALIDOS")
    assert gerencia.status_code == 403


def test_archivo_demasiado_grande(
    crear_cliente: Callable[..., TestClient], configuracion_infra: Callable[..., Configuracion]
) -> None:
    cliente = crear_cliente(configuracion=configuracion_infra(vision_tamanio_maximo_imagen_mb=0.01))

    respuesta = cliente.post(
        "/api/ia/v1/clasificaciones",
        files={"imagen": ("h.jpg", _jpeg(), "image/jpeg")},
        headers=TECNICO,
    )

    assert (respuesta.status_code, respuesta.json()["codigo"]) == (400, "ARCHIVO_DEMASIADO_GRANDE")


def test_sin_modelo_publicado(
    crear_cliente: Callable[..., TestClient], configuracion_infra: Callable[..., Configuracion]
) -> None:
    cliente = crear_cliente(configuracion=configuracion_infra())

    foto = cliente.post(
        "/api/ia/v1/clasificaciones",
        files={"imagen": ("h.jpg", _jpeg(), "image/jpeg")},
        headers=TECNICO,
    )
    metadatos = cliente.get("/api/ia/v1/modelos/clasificador/dispositivo", headers=TECNICO)

    assert (foto.status_code, foto.json()["codigo"]) == (503, "MODELO_NO_DISPONIBLE")
    assert metadatos.status_code == 503


def test_descarga_para_dispositivos(cliente: TestClient) -> None:
    metadatos = cliente.get("/api/ia/v1/modelos/clasificador/dispositivo", headers=TECNICO)

    assert metadatos.status_code == 200
    cuerpo = metadatos.json()
    assert cuerpo["versionModelo"] == "clasificador-1"
    assert [e["categoria"] for e in cuerpo["etiquetas"]] == list(CATEGORIAS)
    assert [e["indice"] for e in cuerpo["etiquetas"]] == list(range(12))
    assert cuerpo["entrada"]["alto"] == 224
    (tflite,) = cuerpo["exportaciones"]["tflite"]["archivos"]
    assert (
        tflite["ruta"]
        == "/api/ia/v1/modelos/clasificador/dispositivo/archivos/tflite/modelo.tflite"
    )

    archivo = cliente.get(tflite["ruta"], headers=TECNICO)
    assert archivo.status_code == 200
    assert archivo.headers["content-type"] == "application/octet-stream"
    assert archivo.headers["etag"] == f'"{tflite["sha256"]}"'
    assert archivo.headers["cache-control"] == "private, max-age=86400"
    assert len(archivo.content) == tflite["tamanio"]
    sin_cambios = cliente.get(
        tflite["ruta"], headers={**TECNICO, "If-None-Match": archivo.headers["etag"]}
    )
    assert sin_cambios.status_code == 304
    assert sin_cambios.content == b""

    for descripcion in cuerpo["exportaciones"]["tfjs"]["archivos"]:
        parte = cliente.get(descripcion["ruta"], headers=TECNICO)
        assert parte.status_code == 200
        assert len(parte.content) == descripcion["tamanio"]
    assert (
        cliente.get(
            "/api/ia/v1/modelos/clasificador/dispositivo/archivos/tfjs/model.json", headers=TECNICO
        ).headers["content-type"]
        == "application/json"
    )

    for ajena in ("modelo.keras", "../otro/modelo.tflite", "tflite/otro.tflite"):
        respuesta = cliente.get(
            f"/api/ia/v1/modelos/clasificador/dispositivo/archivos/{ajena}", headers=TECNICO
        )
        assert respuesta.status_code == 404, ajena
    assert (
        cliente.get("/api/ia/v1/modelos/clasificador/dispositivo", headers=GERENCIA).status_code
        == 403
    )


def test_video_de_punta_a_punta(
    cliente: TestClient, prefijo_s3: str, base_mongo: str, tmp_path: Path
) -> None:
    esperar_rabbitmq(cliente)
    video = crear_video(tmp_path / "v.mp4", 4).read_bytes()

    creado = cliente.post(
        "/api/ia/v1/clasificaciones/videos",
        files={"video": ("campo.mp4", video, "video/mp4")},
        headers=TECNICO,
    )

    assert creado.status_code == 202, creado.text
    final = esperar_estado_final(cliente, creado.json()["idTrabajo"], TECNICO, tiempo_limite=60)
    assert final["estado"] == "COMPLETADO", final
    resultado = final["resultado"]
    assert resultado["categoriaPredominante"] in CATEGORIAS
    assert len(resultado["fotogramas"]) == 4
    assert resultado["clasificacion"]["origen"] == "SERVIDOR"
    temporales = list(
        cliente_s3()
        .list_objects_v2(Bucket=os.environ["AWS_BUCKET"], Prefix=prefijo_s3 + "temporales/")
        .get("Contents", [])
    )
    assert temporales == []


def test_videos_invalidos(cliente: TestClient, tmp_path: Path) -> None:
    falso = cliente.post(
        "/api/ia/v1/clasificaciones/videos",
        files={"video": ("v.mp4", b"no es video", "video/mp4")},
        headers=TECNICO,
    )
    largo = crear_video(tmp_path / "largo.mp4", 61, fps=2, tamanio=(64, 64)).read_bytes()
    demasiado_largo = cliente.post(
        "/api/ia/v1/clasificaciones/videos",
        files={"video": ("v.mp4", largo, "video/mp4")},
        headers=TECNICO,
    )
    grande = cliente.post(
        "/api/ia/v1/clasificaciones/videos",
        files={"video": ("v.mp4", b"0" * (6 * 1024 * 1024), "video/mp4")},
        headers=TECNICO,
    )

    assert (falso.status_code, falso.json()["codigo"]) == (400, "VIDEO_INVALIDO")
    assert (demasiado_largo.status_code, demasiado_largo.json()["codigo"]) == (
        400,
        "VIDEO_INVALIDO",
    )
    assert (grande.status_code, grande.json()["codigo"]) == (400, "ARCHIVO_DEMASIADO_GRANDE")


def test_foto_de_4_mb_en_menos_de_3_segundos(cliente: TestClient) -> None:
    foto = _jpeg(2400, 1800, ruido=True)
    assert len(foto) > 3_500_000

    inicio = time.monotonic()
    respuesta = cliente.post(
        "/api/ia/v1/clasificaciones",
        files={"imagen": ("h.jpg", foto, "image/jpeg")},
        headers=TECNICO,
    )

    assert respuesta.status_code == 201
    assert time.monotonic() - inicio < 3.0
