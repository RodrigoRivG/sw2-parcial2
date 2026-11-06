"""Servicio y manejador `REPORTE` (spec-reportes.md 2.8 y 2.9; historias 1 a 4)."""

import io
import json
import math
import struct
import wave
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from openpyxl import load_workbook

from app.comun.errores import ErrorAplicacion
from app.comun.seguridad import UsuarioAutenticado
from app.integracion.errores import ErrorInfraestructura
from app.integracion.gateway import ClienteGateway
from app.integracion.transcriptor import AudioInvalido, validar_audio
from app.mcp_server.servidor import crear_servidor_mcp
from app.reportes import servicio as modulo
from app.reportes.esquemas import SolicitudTexto
from app.reportes.plan import PlanReporte
from app.reportes.servicio import ServicioReportes, nombre_archivo
from app.trabajos.esquemas import Trabajo
from app.trabajos.estados import EstadoTrabajo
from tests.modelo_guion import ModeloGuion, plan_en_dos_pasos, texto
from tests.transcriptor_fijo import TranscriptorFijo
from tests.unit.mcp_server.conftest import TokenFijo
from tests.unit.reportes.test_fuentes import _servicios
from tests.unit.vision.test_manejador_video import AlmacenMemoria

AHORA = datetime(2026, 11, 6, 16, 0, tzinfo=UTC)
GERENCIA = UsuarioAutenticado("ger", "Gerencia", frozenset({"gerencia"}))
N8N = UsuarioAutenticado("n8n", "n8n", frozenset({"reportes_ia"}))
PLAN = {
    "titulo": "Insumos con stock bajo",
    "formatos": ["PDF", "XLSX"],
    "tablas": [
        {
            "fuente": "INVENTARIO",
            "filtros": [{"campo": "stockBajo", "operador": "igual", "valor": True}],
        }
    ],
}


class Trabajos:
    def __init__(self) -> None:
        self.creados: list[tuple[str, dict[str, Any], str]] = []
        self.guardado: Trabajo | None = None

    async def crear(self, tipo: str, parametros: dict[str, Any], solicitante: Any) -> Trabajo:
        self.creados.append((tipo, parametros, solicitante.id))
        return _trabajo(parametros)

    async def obtener_para(self, id_trabajo: str, solicitante: UsuarioAutenticado) -> Trabajo:
        if self.guardado is None or self.guardado.id_solicitante != solicitante.id:
            raise ErrorAplicacion(404, "TRABAJO_NO_ENCONTRADO")
        return self.guardado


class Eventos:
    def __init__(self, fallos: int = 0) -> None:
        self.fallos = fallos
        self.publicados: list[tuple[str, dict[str, Any]]] = []

    async def publicar_evento(self, routing_key: str, sobre: dict[str, Any]) -> None:
        if self.fallos:
            self.fallos -= 1
            raise ErrorInfraestructura("rabbitmq", "sin conexión")
        self.publicados.append((routing_key, sobre))


def _trabajo(parametros: dict[str, Any], **datos: Any) -> Trabajo:
    valores: dict[str, Any] = {
        "id": "11111111-1111-4111-8111-111111111111",
        "tipo": "REPORTE",
        "estado": EstadoTrabajo.PROCESANDO,
        "id_solicitante": "ger",
        "id_correlacion": "corr-1",
        "parametros": parametros,
        "fecha_creacion": AHORA,
    }
    return Trabajo(**{**valores, **datos})


@asynccontextmanager
async def _servicio(
    modelo: ModeloGuion | None = None,
    eventos: Eventos | None = None,
    transcriptor: TranscriptorFijo | None = None,
    reloj: datetime = AHORA,
) -> AsyncIterator[tuple[ServicioReportes, AlmacenMemoria, Trabajos, Eventos]]:
    almacen, trabajos, eventos = AlmacenMemoria(), Trabajos(), eventos or Eventos()
    async with httpx.AsyncClient(transport=httpx.MockTransport(_servicios())) as http:
        gateway = ClienteGateway(http, "http://gateway.prueba", TokenFijo(), 1.0)
        servicio = ServicioReportes(
            modelo or ModeloGuion(),
            crear_servidor_mcp(gateway),
            trabajos,  # type: ignore[arg-type]
            almacen,
            eventos,
            transcriptor or TranscriptorFijo(),
            7,
            lambda: reloj,
        )
        yield servicio, almacen, trabajos, eventos


@pytest.fixture(autouse=True)
def _sin_esperas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo, "ESPERAS_EVENTO", (0.0, 0.0, 0.0))


def _wav(segundos: float) -> bytes:
    salida = io.BytesIO()
    with wave.open(salida, "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(8000)
        muestras = (int(3000 * math.sin(i / 8)) for i in range(int(8000 * segundos)))
        archivo.writeframes(b"".join(struct.pack("<h", m) for m in muestras))
    return salida.getvalue()


# --- manejador -----------------------------------------------------------------------------


async def test_plan_ya_armado_genera_pdf_y_excel_y_publica_el_evento() -> None:
    modelo = ModeloGuion(texto("Glifosato tiene 20.000 litros y está bajo el mínimo."))

    async with _servicio(modelo) as (servicio, almacen, _, eventos):
        plan = PlanReporte.model_validate(PLAN).model_dump(mode="json", by_alias=True)
        resultado = await servicio.procesar(_trabajo({"origen": "PROGRAMADO", "plan": plan}))

    assert resultado["origen"] == "PROGRAMADO" and resultado["transcripcion"] is None
    assert resultado["titulo"] == "Insumos con stock bajo"
    assert resultado["resumen"] == "Glifosato tiene 20.000 litros y está bajo el mínimo."
    assert resultado["tablas"][0]["filas"][0][0] == "Glifosato"
    assert resultado["fechaExpiracionArchivos"] == "2026-11-13T16:00:00Z"
    pdf, xlsx = resultado["archivos"]
    assert pdf["nombre"] == "reporte-insumos-con-stock-bajo-2026-11-06.pdf"
    assert pdf["ruta"] == "/api/ia/v1/reportes/11111111-1111-4111-8111-111111111111/archivos/PDF"
    ruta_xlsx = f"reportes/11111111-1111-4111-8111-111111111111/{xlsx['nombre']}"
    assert almacen.archivos[ruta_xlsx][:2] == b"PK"
    assert load_workbook(io.BytesIO(almacen.archivos[ruta_xlsx])).sheetnames == [
        "Reporte",
        "Inventario de insumos",
    ]
    ((ruta, sobre),) = eventos.publicados
    assert ruta == "ia.reporte.completado" and sobre["tipo"] == "ReporteCompletado"
    assert sobre["idCorrelacion"] == "corr-1"
    assert (
        sobre["datos"]["origen"] == "PROGRAMADO"
        and sobre["datos"]["archivos"][0]["formato"] == "PDF"
    )
    assert "sha256" not in sobre["datos"]["archivos"][0]
    assert json.dumps(resultado)  # serializable para guardarlo en el trabajo


async def test_texto_interpretado_por_el_modelo() -> None:
    plan = {**PLAN, "formatos": ["PDF"], "incluirResumen": False, "noAtendido": []}
    modelo = ModeloGuion(*plan_en_dos_pasos(plan))

    async with _servicio(modelo) as (servicio, almacen, _, _):
        resultado = await servicio.procesar(
            _trabajo(
                {"origen": "SOLICITADO", "texto": "Insumos con stock bajo", "formatos": ["XLSX"]}
            )
        )

    assert resultado["textoSolicitud"] == "Insumos con stock bajo"
    assert [a["formato"] for a in resultado["archivos"]] == ["XLSX"]  # los de la solicitud
    assert resultado["resumen"] is None
    assert resultado["modeloLenguaje"] == "modelo-guion"


async def test_voz_transcribe_y_borra_el_audio() -> None:
    plan = {**PLAN, "formatos": ["PDF"], "incluirResumen": False, "noAtendido": []}
    transcriptor = TranscriptorFijo("Quiero el reporte de insumos con stock bajo")

    async with _servicio(ModeloGuion(*plan_en_dos_pasos(plan)), transcriptor=transcriptor) as (
        servicio,
        almacen,
        _,
        _,
    ):
        almacen.archivos["temporales/audios/a.webm"] = b"audio"
        resultado = await servicio.procesar(
            _trabajo({"origen": "SOLICITADO", "rutaAudio": "temporales/audios/a.webm"})
        )

    assert resultado["transcripcion"] == "Quiero el reporte de insumos con stock bajo"
    assert transcriptor.recibidos == [b"audio"]
    assert almacen.borrados == ["temporales/audios/a.webm"]


@pytest.mark.parametrize(
    ("transcriptor", "codigo"),
    [
        (TranscriptorFijo("  "), "AUDIO_SIN_VOZ"),
        (TranscriptorFijo(disponible=False), "TRANSCRIPTOR_NO_DISPONIBLE"),
    ],
)
async def test_voz_que_falla_tambien_borra_el_audio(
    transcriptor: TranscriptorFijo, codigo: str
) -> None:
    async with _servicio(transcriptor=transcriptor) as (servicio, almacen, _, _):
        almacen.archivos["temporales/audios/a.webm"] = b"audio"
        with pytest.raises(ErrorAplicacion) as error:
            await servicio.procesar(
                _trabajo({"origen": "SOLICITADO", "rutaAudio": "temporales/audios/a.webm"})
            )

    assert error.value.codigo == codigo
    assert almacen.borrados == ["temporales/audios/a.webm"]


async def test_evento_no_publicado_segun_origen() -> None:
    plan = PlanReporte.model_validate({**PLAN, "incluirResumen": False}).model_dump(
        mode="json", by_alias=True
    )

    async with _servicio(eventos=Eventos(fallos=4)) as (servicio, _, _, eventos):
        with pytest.raises(ErrorAplicacion) as error:
            await servicio.procesar(_trabajo({"origen": "PROGRAMADO", "plan": plan}))
    async with _servicio(eventos=Eventos(fallos=4)) as (servicio, _, _, _):
        resultado = await servicio.procesar(_trabajo({"origen": "SOLICITADO", "plan": plan}))
    async with _servicio(eventos=Eventos(fallos=3)) as (servicio, _, _, eventos):
        await servicio.procesar(_trabajo({"origen": "PROGRAMADO", "plan": plan}))

    assert error.value.codigo == "EVENTO_NO_PUBLICADO"
    assert resultado["archivos"]  # el de gerencia termina igual
    assert len(eventos.publicados) == 1  # al cuarto intento


async def test_error_del_agente_llega_como_error_del_trabajo() -> None:
    from app.integracion.modelo_lenguaje import ModeloLenguajeNoDisponible

    async with _servicio(ModeloGuion(ModeloLenguajeNoDisponible())) as (servicio, _, _, _):
        with pytest.raises(ErrorAplicacion) as caido:
            await servicio.procesar(_trabajo({"origen": "SOLICITADO", "texto": "Insumos"}))
    async with _servicio(ModeloGuion(texto('{"fuentes": []}'))) as (servicio, _, _, _):
        with pytest.raises(ErrorAplicacion) as no_soportado:
            await servicio.procesar(_trabajo({"origen": "SOLICITADO", "texto": "El clima"}))

    assert caido.value.codigo == "MODELO_LENGUAJE_NO_DISPONIBLE"
    assert no_soportado.value.codigo == "REPORTE_NO_SOPORTADO"


# --- solicitudes ---------------------------------------------------------------------------


async def test_solicitar_plan_valido_invalido_y_origen() -> None:
    async with _servicio() as (servicio, _, trabajos, _):
        await servicio.solicitar(PlanReporte.model_validate(PLAN), N8N)
        await servicio.solicitar(PlanReporte.model_validate(PLAN), GERENCIA)
        with pytest.raises(ErrorAplicacion) as error:
            await servicio.solicitar(
                PlanReporte.model_validate(
                    {"tablas": [{"fuente": "INVENTARIO", "columnas": ["precio"]}]}
                ),
                N8N,
            )

    assert [(c[1]["origen"], c[2]) for c in trabajos.creados] == [
        ("PROGRAMADO", "n8n"),
        ("SOLICITADO", "ger"),
    ]
    assert trabajos.creados[0][1]["plan"]["tablas"][0]["fuente"] == "INVENTARIO"
    assert (
        error.value.estado_http == 400 and error.value.detalles[0].campo == "tablas[0].columnas[0]"
    )


async def test_solicitar_texto_falla_rapido_sin_modelo() -> None:
    async with _servicio(ModeloGuion(disponible=False)) as (servicio, _, trabajos, _):
        with pytest.raises(ErrorAplicacion) as error:
            await servicio.solicitar(SolicitudTexto(texto="Insumos con stock bajo"), GERENCIA)

    assert (error.value.estado_http, error.value.codigo) == (503, "MODELO_LENGUAJE_NO_DISPONIBLE")
    assert trabajos.creados == []


async def test_solicitar_voz_valida_sube_el_audio(tmp_path: Path) -> None:
    valido, largo, roto = tmp_path / "a.wav", tmp_path / "b.wav", tmp_path / "c.wav"
    valido.write_bytes(_wav(2))
    largo.write_bytes(_wav(121))
    roto.write_bytes(b"no es audio")

    async with _servicio() as (servicio, almacen, trabajos, _):
        await servicio.solicitar_voz(valido, None, GERENCIA)
        for archivo in (largo, roto):
            with pytest.raises(ErrorAplicacion) as error:
                await servicio.solicitar_voz(archivo, None, GERENCIA)
            assert error.value.codigo == "AUDIO_INVALIDO"

    ((tipo, parametros, _),) = trabajos.creados
    assert parametros["origen"] == "SOLICITADO" and parametros["rutaAudio"].endswith(".wav")
    assert almacen.archivos[parametros["rutaAudio"]] == valido.read_bytes()


def test_validar_audio_webm_sin_duracion_en_la_cabecera(tmp_path: Path) -> None:
    import av
    import numpy as np

    ruta = tmp_path / "grabado.webm"
    with av.open(str(ruta), "w", format="webm") as salida:
        pista = salida.add_stream("libopus", rate=48000)
        pista.layout = "mono"
        for i in range(150):  # 3 s en cuadros de 20 ms
            muestras = (np.sin(np.arange(960) / 10 + i) * 8000).astype(np.int16).reshape(1, -1)
            cuadro = av.AudioFrame.from_ndarray(muestras, format="s16", layout="mono")
            cuadro.sample_rate = 48000
            for paquete in pista.encode(cuadro):
                salida.mux(paquete)
        for paquete in pista.encode(None):
            salida.mux(paquete)

    assert 2.5 < validar_audio(ruta) < 3.5
    with pytest.raises(AudioInvalido):
        validar_audio(tmp_path / "no-existe.webm")


# --- descarga ------------------------------------------------------------------------------


async def test_descargas() -> None:
    plan = PlanReporte.model_validate({**PLAN, "incluirResumen": False}).model_dump(
        mode="json", by_alias=True
    )
    async with _servicio() as (servicio, almacen, trabajos, _):
        resultado = await servicio.procesar(_trabajo({"origen": "SOLICITADO", "plan": plan}))
        trabajos.guardado = _trabajo({}, estado=EstadoTrabajo.COMPLETADO, resultado=resultado)

        archivo = await servicio.descargar(trabajos.guardado.id, "pdf", GERENCIA)
        assert archivo.datos.startswith(b"%PDF") and archivo.tipo_contenido == "application/pdf"
        assert archivo.sha256 == resultado["archivos"][0]["sha256"]

        errores = {}
        for caso, (id_, formato, usuario) in {
            "ajeno": (trabajos.guardado.id, "PDF", N8N),
            "formato": (trabajos.guardado.id, "CSV", GERENCIA),
        }.items():
            with pytest.raises(ErrorAplicacion) as error:
                await servicio.descargar(id_, formato, usuario)
            errores[caso] = error.value.codigo
        assert errores == {"ajeno": "REPORTE_NO_ENCONTRADO", "formato": "REPORTE_NO_ENCONTRADO"}

        trabajos.guardado = _trabajo({}, estado=EstadoTrabajo.EN_COLA)
        with pytest.raises(ErrorAplicacion) as en_proceso:
            await servicio.descargar(trabajos.guardado.id, "PDF", GERENCIA)
        assert (en_proceso.value.estado_http, en_proceso.value.codigo) == (
            409,
            "REPORTE_EN_PROCESO",
        )

        trabajos.guardado = _trabajo({}, estado=EstadoTrabajo.COMPLETADO, resultado=resultado)
        almacen.archivos.clear()  # el ciclo de vida del bucket los borró
        with pytest.raises(ErrorAplicacion) as borrado:
            await servicio.descargar(trabajos.guardado.id, "PDF", GERENCIA)
        assert borrado.value.codigo == "REPORTE_EXPIRADO"

    async with _servicio(reloj=AHORA + timedelta(days=7)) as (servicio, _, trabajos, _):
        trabajos.guardado = _trabajo({}, estado=EstadoTrabajo.COMPLETADO, resultado=resultado)
        with pytest.raises(ErrorAplicacion) as vencido:
            await servicio.descargar(trabajos.guardado.id, "PDF", GERENCIA)
        assert vencido.value.codigo == "REPORTE_EXPIRADO"


def test_nombre_de_archivo_sin_tildes_ni_espacios() -> None:
    from app.reportes.plan import FormatoReporte

    nombre = nombre_archivo("Campañas de Maíz: año 2026 / costos!", AHORA, FormatoReporte.XLSX)

    assert nombre == "reporte-campanas-de-maiz-ano-2026-costos-2026-11-06.xlsx"
