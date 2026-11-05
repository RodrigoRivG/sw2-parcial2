"""ConsumidorTrabajos.procesar: spec-trabajos.md 2.9 (Historias 2, 3 y 4)."""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from app.comun.correlacion import id_correlacion_actual
from app.comun.errores import ErrorAplicacion
from app.trabajos.consumidor import ConsumidorTrabajos
from app.trabajos.esquemas import Trabajo
from app.trabajos.estados import EstadoTrabajo
from app.trabajos.registro import DefinicionTipo, Manejador, RegistroTipos
from tests.dobles import RepositorioTrabajosMemoria

AHORA = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


class Mensaje:
    def __init__(self) -> None:
        self.acciones: list[str] = []

    async def confirmar(self) -> None:
        self.acciones.append("ack")

    async def descartar(self) -> None:
        self.acciones.append("dlq")


class Esperas:
    def __init__(self) -> None:
        self.segundos: list[float] = []

    async def __call__(self, segundos: float) -> None:
        self.segundos.append(segundos)


@pytest.fixture
def repositorio() -> RepositorioTrabajosMemoria:
    return RepositorioTrabajosMemoria()


@pytest.fixture
def esperas() -> Esperas:
    return Esperas()


def _consumidor(
    repositorio: RepositorioTrabajosMemoria,
    esperas: Esperas,
    manejador: Manejador,
    limite: timedelta = timedelta(seconds=2),
) -> ConsumidorTrabajos:
    registro = RegistroTipos()
    registro.registrar(DefinicionTipo("PRUEBA", manejador, limite))
    return ConsumidorTrabajos(repositorio, registro, 30, reloj=lambda: AHORA, esperar=esperas)  # type: ignore[arg-type]


def _trabajo(
    repositorio: RepositorioTrabajosMemoria, tipo: str = "PRUEBA", estado: str = "EN_COLA"
) -> str:
    trabajo = Trabajo(
        id=str(uuid.uuid4()),
        tipo=tipo,
        estado=EstadoTrabajo(estado),
        id_solicitante="ana",
        id_correlacion="corr-1",
        parametros={"n": 2},
        fecha_creacion=AHORA,
    )
    repositorio.documentos[trabajo.id] = trabajo.a_documento()
    return trabajo.id


def _sobre(id_trabajo: str) -> bytes:
    return json.dumps(
        {
            "idMensaje": "m",
            "idCorrelacion": "corr-1",
            "tipo": "ProcesarTrabajo",
            "datos": {"idTrabajo": id_trabajo},
        }
    ).encode()


async def _procesar(consumidor: ConsumidorTrabajos, cuerpo: bytes) -> Mensaje:
    mensaje = Mensaje()
    await consumidor.procesar(cuerpo, mensaje.confirmar, mensaje.descartar)
    return mensaje


async def _eco(trabajo: Trabajo) -> dict[str, Any]:
    return {"doble": trabajo.parametros["n"] * 2, "correlacion": id_correlacion_actual.get()}


async def test_exito_pasa_por_procesando_y_termina_completado(
    repositorio: RepositorioTrabajosMemoria, esperas: Esperas
) -> None:
    id_trabajo = _trabajo(repositorio)

    mensaje = await _procesar(_consumidor(repositorio, esperas, _eco), _sobre(id_trabajo))

    documento = repositorio.documentos[id_trabajo]
    assert mensaje.acciones == ["ack"]
    assert documento["estado"] == "COMPLETADO"
    assert documento["resultado"] == {"doble": 4, "correlacion": "corr-1"}
    assert documento["fechaInicio"] == AHORA
    assert documento["fechaLimite"] == AHORA + timedelta(seconds=32)
    assert documento["fechaFin"] == AHORA
    assert documento["fechaExpiracion"] == AHORA + timedelta(days=30)


async def test_error_esperado_queda_con_su_codigo(
    repositorio: RepositorioTrabajosMemoria, esperas: Esperas
) -> None:
    async def manejador(_: Trabajo) -> dict[str, Any]:
        raise ErrorAplicacion(
            503, "MODELO_LENGUAJE_NO_DISPONIBLE", "El asistente no está disponible."
        )

    id_trabajo = _trabajo(repositorio)
    await _procesar(_consumidor(repositorio, esperas, manejador), _sobre(id_trabajo))

    documento = repositorio.documentos[id_trabajo]
    assert documento["estado"] == "FALLIDO"
    assert documento["error"] == {
        "codigo": "MODELO_LENGUAJE_NO_DISPONIBLE",
        "mensaje": "El asistente no está disponible.",
    }


async def test_error_inesperado_es_error_interno_sin_traza_y_sin_reintento(
    repositorio: RepositorioTrabajosMemoria, esperas: Esperas, caplog: pytest.LogCaptureFixture
) -> None:
    llamadas = 0

    async def manejador(_: Trabajo) -> dict[str, Any]:
        nonlocal llamadas
        llamadas += 1
        raise RuntimeError("detalle interno")

    id_trabajo = _trabajo(repositorio)
    await _procesar(_consumidor(repositorio, esperas, manejador), _sobre(id_trabajo))

    documento = repositorio.documentos[id_trabajo]
    assert llamadas == 1
    assert documento["error"] == {
        "codigo": "ERROR_INTERNO",
        "mensaje": "Ocurrió un error inesperado.",
    }
    assert "detalle interno" not in json.dumps(documento, default=str)
    assert "detalle interno" in caplog.text


async def test_tiempo_limite_agotado(
    repositorio: RepositorioTrabajosMemoria, esperas: Esperas
) -> None:
    async def lento(_: Trabajo) -> dict[str, Any]:
        await asyncio.sleep(5)
        return {"tarde": True}

    id_trabajo = _trabajo(repositorio)
    consumidor = _consumidor(repositorio, esperas, lento, limite=timedelta(milliseconds=50))
    await _procesar(consumidor, _sobre(id_trabajo))

    documento = repositorio.documentos[id_trabajo]
    assert documento["estado"] == "FALLIDO"
    assert documento["error"]["codigo"] == "TIEMPO_AGOTADO"
    assert "resultado" not in documento or documento["resultado"] is None


@pytest.mark.parametrize(
    "resultado",
    [{"texto": "x" * 100_001}, {"monto": Decimal("1.00")}],
    ids=["mayor-a-100kb", "no-es-json"],
)
async def test_resultado_invalido_es_error_interno(
    repositorio: RepositorioTrabajosMemoria, esperas: Esperas, resultado: dict[str, Any]
) -> None:
    async def manejador(_: Trabajo) -> dict[str, Any]:
        return resultado

    id_trabajo = _trabajo(repositorio)
    await _procesar(_consumidor(repositorio, esperas, manejador), _sobre(id_trabajo))

    assert repositorio.documentos[id_trabajo]["error"]["codigo"] == "ERROR_INTERNO"


@pytest.mark.parametrize("estado", ["PROCESANDO", "COMPLETADO", "FALLIDO"])
async def test_trabajo_que_ya_no_esta_en_cola_se_confirma_sin_ejecutar(
    repositorio: RepositorioTrabajosMemoria, esperas: Esperas, estado: str
) -> None:
    ejecutado = False

    async def manejador(_: Trabajo) -> dict[str, Any]:
        nonlocal ejecutado
        ejecutado = True
        return {}

    id_trabajo = _trabajo(repositorio, estado=estado)
    mensaje = await _procesar(_consumidor(repositorio, esperas, manejador), _sobre(id_trabajo))

    assert mensaje.acciones == ["ack"]
    assert not ejecutado
    assert repositorio.documentos[id_trabajo]["estado"] == estado


async def test_duplicados_simultaneos_ejecutan_una_sola_vez(
    repositorio: RepositorioTrabajosMemoria, esperas: Esperas
) -> None:
    ejecuciones = 0

    async def manejador(_: Trabajo) -> dict[str, Any]:
        nonlocal ejecuciones
        ejecuciones += 1
        await asyncio.sleep(0.01)
        return {}

    id_trabajo = _trabajo(repositorio)
    consumidor = _consumidor(repositorio, esperas, manejador)
    mensajes = await asyncio.gather(*(_procesar(consumidor, _sobre(id_trabajo)) for _ in range(20)))

    assert ejecuciones == 1
    assert all(m.acciones == ["ack"] for m in mensajes)


@pytest.mark.parametrize(
    "cuerpo",
    [b"no es json", b"{}", json.dumps({"datos": {"idTrabajo": "no-uuid"}}).encode()],
    ids=["texto", "sin-datos", "id-invalido"],
)
async def test_sobre_no_interpretable_va_a_la_dlq(
    repositorio: RepositorioTrabajosMemoria, esperas: Esperas, cuerpo: bytes
) -> None:
    mensaje = await _procesar(_consumidor(repositorio, esperas, _eco), cuerpo)

    assert mensaje.acciones == ["dlq"]


async def test_trabajo_inexistente_va_a_la_dlq(
    repositorio: RepositorioTrabajosMemoria, esperas: Esperas
) -> None:
    mensaje = await _procesar(_consumidor(repositorio, esperas, _eco), _sobre(str(uuid.uuid4())))

    assert mensaje.acciones == ["dlq"]


async def test_tipo_no_registrado_queda_fallido(
    repositorio: RepositorioTrabajosMemoria, esperas: Esperas
) -> None:
    id_trabajo = _trabajo(repositorio, tipo="OTRO")

    mensaje = await _procesar(_consumidor(repositorio, esperas, _eco), _sobre(id_trabajo))

    assert mensaje.acciones == ["ack"]
    assert repositorio.documentos[id_trabajo]["error"]["codigo"] == "ERROR_INTERNO"


async def test_falla_pasajera_de_firestore_se_reintenta(
    repositorio: RepositorioTrabajosMemoria, esperas: Esperas
) -> None:
    id_trabajo = _trabajo(repositorio)
    repositorio.fallas["obtener"] = 2

    mensaje = await _procesar(_consumidor(repositorio, esperas, _eco), _sobre(id_trabajo))

    assert esperas.segundos == [1.0, 2.0]
    assert mensaje.acciones == ["ack"]
    assert repositorio.documentos[id_trabajo]["estado"] == "COMPLETADO"


async def test_falla_persistente_de_firestore_va_a_la_dlq_tras_tres_reintentos(
    repositorio: RepositorioTrabajosMemoria, esperas: Esperas
) -> None:
    id_trabajo = _trabajo(repositorio)
    repositorio.fallas["cambiar_estado"] = 10

    mensaje = await _procesar(_consumidor(repositorio, esperas, _eco), _sobre(id_trabajo))

    assert esperas.segundos == [1.0, 2.0, 4.0]
    assert mensaje.acciones == ["dlq"]
    assert repositorio.documentos[id_trabajo]["estado"] == "EN_COLA"


async def test_falla_al_iniciar_el_consumidor_queda_en_el_log(
    repositorio: RepositorioTrabajosMemoria, esperas: Esperas, caplog: pytest.LogCaptureFixture
) -> None:
    class ConexionRota:
        async def cola_de_consumo(self, prefetch: int) -> Any:
            raise RuntimeError("canal cerrado")

    consumidor = _consumidor(repositorio, esperas, _eco)
    consumidor.iniciar(ConexionRota(), 2)  # type: ignore[arg-type]
    await asyncio.sleep(0.01)

    assert "La tarea de fondo terminó con error" in caplog.text
    await consumidor.detener()
