"""Endpoints de reportes con MongoDB, S3 y RabbitMQ de los emuladores
(spec-reportes.md 2.10 y 2.13; historias 1 a 4; CE-REP-02)."""

import asyncio
import json
import time
import uuid
from collections.abc import Callable
from typing import Any

import aio_pika
import httpx
from fastapi.testclient import TestClient

from app.config import Configuracion
from app.integracion.gateway import ClienteGateway
from app.mcp_server.servidor import crear_servidor_mcp
from app.reportes.servicio import ServicioReportes
from tests.conftest import RABBITMQ_URL, autorizacion, emitir_token
from tests.integration.conftest import esperar_estado_final, esperar_rabbitmq
from tests.modelo_guion import ModeloGuion, plan_en_dos_pasos, texto
from tests.transcriptor_fijo import TranscriptorFijo
from tests.unit.mcp_server.conftest import TokenFijo
from tests.unit.reportes.test_fuentes import _servicios
from tests.unit.reportes.test_manejador import _wav

RUTA = "/api/ia/v1/reportes"
GERENCIA = autorizacion(emitir_token(["gerencia"], sub="ana"))
N8N = autorizacion(emitir_token(["reportes_ia"], sub="n8n"))
TECNICO = autorizacion(emitir_token(["tecnico_campo"]))
PLAN = {
    "titulo": "Insumos con stock bajo",
    "formatos": ["PDF", "XLSX"],
    "incluirResumen": False,
    "tablas": [
        {
            "fuente": "INVENTARIO",
            "filtros": [{"campo": "stockBajo", "operador": "igual", "valor": True}],
        }
    ],
}


def _usar(
    cliente: TestClient, modelo: ModeloGuion, transcriptor: TranscriptorFijo | None = None
) -> None:
    """Ollama, Whisper y los servicios son dobles; MongoDB, S3 y RabbitMQ son reales."""
    estado = cliente.app.state  # type: ignore[attr-defined]
    http = httpx.AsyncClient(transport=httpx.MockTransport(_servicios()))
    gateway = ClienteGateway(http, "http://gateway.prueba", TokenFijo(), 1.0)
    estado.modelo_lenguaje = modelo
    estado.servicio_reportes = ServicioReportes(
        modelo,
        crear_servidor_mcp(gateway),
        estado.servicio_trabajos,
        estado.almacen_archivos,
        estado.conexion_rabbitmq,
        transcriptor or TranscriptorFijo(),
        7,
    )


def _cola_de_eventos() -> str:
    """Una cola propia enlazada a `eventos`, como haría n8n (constitución §10)."""
    nombre = f"prueba-reportes-{uuid.uuid4().hex[:8]}"

    async def crear() -> None:
        async with await aio_pika.connect(RABBITMQ_URL) as conexion:
            canal = await conexion.channel()
            cola = await canal.declare_queue(
                nombre, durable=True
            )  # RabbitMQ 4 no admite colas transitorias compartidas
            await cola.bind("eventos", routing_key="ia.reporte.completado")

    asyncio.run(crear())
    return nombre


def _leer_evento(nombre: str) -> dict[str, Any]:
    async def leer() -> dict[str, Any]:
        async with await aio_pika.connect(RABBITMQ_URL) as conexion:
            canal = await conexion.channel()
            cola = await canal.get_queue(nombre)
            for _ in range(50):
                mensaje = await cola.get(no_ack=True, fail=False)
                if mensaje is not None:
                    await cola.delete(if_unused=False, if_empty=False)
                    datos: dict[str, Any] = json.loads(mensaje.body)
                    return datos
                await asyncio.sleep(0.1)
            await cola.delete(if_unused=False, if_empty=False)
            raise AssertionError("No llegó el evento")

    return asyncio.run(leer())


def test_permisos_y_validacion(cliente: TestClient) -> None:
    _usar(cliente, ModeloGuion(disponible=False))

    assert cliente.post(RUTA, json=PLAN).status_code == 401
    assert cliente.post(RUTA, json=PLAN, headers=TECNICO).json()["codigo"] == "SIN_PERMISO"
    assert cliente.get(f"{RUTA}/fuentes", headers=TECNICO).status_code == 403
    voz = cliente.post(f"{RUTA}/voz", files={"audio": ("a.wav", _wav(1), "audio/wav")}, headers=N8N)
    assert (voz.status_code, voz.json()["codigo"]) == (403, "SIN_PERMISO")

    invalido = cliente.post(
        RUTA, json={"tablas": [{"fuente": "INVENTARIO", "columnas": ["precio"]}]}, headers=N8N
    )
    assert invalido.status_code == 400
    assert invalido.json()["detalles"][0]["campo"] == "tablas[0].columnas[0]"
    ambos = cliente.post(RUTA, json={**PLAN, "texto": "Insumos"}, headers=GERENCIA)
    assert ambos.status_code == 400
    sin_modelo = cliente.post(RUTA, json={"texto": "Insumos con stock bajo"}, headers=GERENCIA)
    assert (sin_modelo.status_code, sin_modelo.json()["codigo"]) == (
        503,
        "MODELO_LENGUAJE_NO_DISPONIBLE",
    )


def test_catalogo_de_fuentes(cliente: TestClient) -> None:
    fuentes = cliente.get(f"{RUTA}/fuentes", headers=N8N).json()

    assert len(fuentes) == 10
    inventario = next(f for f in fuentes if f["nombre"] == "INVENTARIO")
    stock = next(c for c in inventario["campos"] if c["nombre"] == "stock")
    assert stock["tipo"] == "DECIMAL" and "entre" in stock["operadores"] and stock["porDefecto"]
    assert next(f for f in fuentes if f["nombre"] == "COSTOS_CAMPANIA")["deUnaCampania"] is True


def test_audio_invalido_o_demasiado_grande(
    crear_cliente: Callable[..., TestClient], configuracion_infra: Callable[..., Configuracion]
) -> None:
    cliente = crear_cliente(
        configuracion=configuracion_infra(reportes_tamanio_maximo_audio_mb=0.05)
    )
    _usar(cliente, ModeloGuion())

    roto = cliente.post(
        f"{RUTA}/voz", files={"audio": ("a.mp3", b"no es audio", "audio/mpeg")}, headers=GERENCIA
    )
    grande = cliente.post(
        f"{RUTA}/voz", files={"audio": ("a.wav", _wav(10), "audio/wav")}, headers=GERENCIA
    )

    assert (roto.status_code, roto.json()["codigo"]) == (400, "AUDIO_INVALIDO")
    assert (grande.status_code, grande.json()["codigo"]) == (400, "ARCHIVO_DEMASIADO_GRANDE")


def test_plan_de_n8n_de_punta_a_punta_con_evento_y_descarga(
    crear_cliente: Callable[..., TestClient], configuracion_infra: Callable[..., Configuracion]
) -> None:
    cliente = crear_cliente(configuracion=configuracion_infra())
    esperar_rabbitmq(cliente)
    _usar(cliente, ModeloGuion())
    cola = _cola_de_eventos()
    inicio = time.monotonic()

    creado = cliente.post(RUTA, json=PLAN, headers=N8N)
    trabajo = esperar_estado_final(cliente, creado.json()["idTrabajo"], N8N, tiempo_limite=30)

    assert time.monotonic() - inicio < 15  # CE-REP-02
    assert trabajo["estado"] == "COMPLETADO", trabajo
    resultado = trabajo["resultado"]
    assert resultado["origen"] == "PROGRAMADO" and resultado["resumen"] is None
    assert [a["formato"] for a in resultado["archivos"]] == ["PDF", "XLSX"]
    evento = _leer_evento(cola)
    assert evento["tipo"] == "ReporteCompletado" and evento["datos"]["origen"] == "PROGRAMADO"
    assert evento["datos"]["idTrabajo"] == creado.json()["idTrabajo"]
    assert evento["idCorrelacion"] == creado.headers["X-Correlation-Id"]

    ruta = resultado["archivos"][0]["ruta"]
    pdf = cliente.get(ruta, headers=N8N)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"].startswith(
        'attachment; filename="reporte-insumos-con-stock-bajo-'
    )
    assert (
        cliente.get(ruta, headers={**N8N, "If-None-Match": pdf.headers["ETag"]}).status_code == 304
    )
    ajeno = cliente.get(ruta, headers=GERENCIA)
    assert (ajeno.status_code, ajeno.json()["codigo"]) == (404, "REPORTE_NO_ENCONTRADO")
    xlsx = cliente.get(resultado["archivos"][1]["ruta"], headers=N8N)
    assert xlsx.content[:2] == b"PK"


def test_reporte_por_voz_de_gerencia(
    crear_cliente: Callable[..., TestClient], configuracion_infra: Callable[..., Configuracion]
) -> None:
    cliente = crear_cliente(configuracion=configuracion_infra())
    esperar_rabbitmq(cliente)
    plan = {**PLAN, "formatos": ["PDF"], "incluirResumen": True, "noAtendido": []}
    _usar(
        cliente,
        ModeloGuion(*plan_en_dos_pasos(plan), texto("Glifosato está en su nivel mínimo.")),
        TranscriptorFijo("Quiero el reporte de insumos con stock bajo"),
    )

    creado = cliente.post(
        f"{RUTA}/voz",
        files={"audio": ("grabacion.wav", _wav(2), "audio/wav")},
        data={"formatos": ["XLSX"]},
        headers=GERENCIA,
    )
    trabajo = esperar_estado_final(cliente, creado.json()["idTrabajo"], GERENCIA, tiempo_limite=30)

    assert creado.status_code == 202
    assert trabajo["estado"] == "COMPLETADO", trabajo
    resultado = trabajo["resultado"]
    assert resultado["transcripcion"] == "Quiero el reporte de insumos con stock bajo"
    assert resultado["origen"] == "SOLICITADO"
    assert [a["formato"] for a in resultado["archivos"]] == ["XLSX"]
    assert resultado["resumen"] == "Glifosato está en su nivel mínimo."


def test_descarga_de_un_reporte_en_proceso(
    crear_cliente: Callable[..., TestClient], configuracion_infra: Callable[..., Configuracion]
) -> None:
    cliente = crear_cliente(configuracion=configuracion_infra(trabajos_consumidor_activo=False))
    esperar_rabbitmq(cliente)
    _usar(cliente, ModeloGuion())

    creado = cliente.post(RUTA, json=PLAN, headers=N8N)
    respuesta = cliente.get(f"{RUTA}/{creado.json()['idTrabajo']}/archivos/PDF", headers=N8N)

    assert (respuesta.status_code, respuesta.json()["codigo"]) == (409, "REPORTE_EN_PROCESO")
    inexistente = cliente.get(f"{RUTA}/{uuid.uuid4()}/archivos/PDF", headers=N8N)
    assert inexistente.json()["codigo"] == "REPORTE_NO_ENCONTRADO"
