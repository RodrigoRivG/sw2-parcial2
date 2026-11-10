"""ServicioTrabajos: crear (Historia 1, escenario 1; Historia 4, escenarios 2 y 3) y obtener."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.comun.correlacion import id_correlacion_actual
from app.comun.errores import ErrorAplicacion
from app.comun.seguridad import UsuarioAutenticado
from app.trabajos.esquemas import Trabajo
from app.trabajos.registro import DefinicionTipo, RegistroTipos
from app.trabajos.servicio import ServicioTrabajos, respuesta_creado
from tests.dobles import PublicadorFalso, RepositorioTrabajosMemoria

AHORA = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
ANA = UsuarioAutenticado(id="ana", nombre="Ana", roles=frozenset({"gerencia"}))
LUIS = UsuarioAutenticado(id="luis", nombre="Luis", roles=frozenset({"gerencia"}))


async def _manejador(trabajo: Trabajo) -> dict[str, Any]:
    return {}


@pytest.fixture
def repositorio() -> RepositorioTrabajosMemoria:
    return RepositorioTrabajosMemoria()


def _servicio(
    repositorio: RepositorioTrabajosMemoria, publicador: PublicadorFalso
) -> ServicioTrabajos:
    registro = RegistroTipos()
    registro.registrar(DefinicionTipo("PRUEBA", _manejador, timedelta(seconds=5)))
    return ServicioTrabajos(repositorio, publicador, registro, 30, reloj=lambda: AHORA)  # type: ignore[arg-type]


async def test_crear_guarda_en_cola_y_publica_con_la_correlacion(
    repositorio: RepositorioTrabajosMemoria,
) -> None:
    publicador = PublicadorFalso()
    contexto = id_correlacion_actual.set("corr-9")
    try:
        trabajo = await _servicio(repositorio, publicador).crear("PRUEBA", {"x": 1}, ANA)
    finally:
        id_correlacion_actual.reset(contexto)

    documento = repositorio.documentos[trabajo.id]
    assert documento["estado"] == "EN_COLA"
    assert documento["idSolicitante"] == "ana"
    assert documento["idCorrelacion"] == "corr-9"
    assert documento["parametros"] == {"x": 1}
    assert documento["fechaCreacion"] == AHORA
    cola, sobre = publicador.publicados[0]
    assert cola == PublicadorFalso.cola_trabajos
    assert sobre["tipo"] == "ProcesarTrabajo"
    assert sobre["datos"] == {"idTrabajo": trabajo.id}
    assert sobre["idCorrelacion"] == "corr-9"
    assert repositorio.llamadas.index("guardar_nuevo") == 0  # se guarda antes de encolar


async def test_crear_respuesta_202_con_location(repositorio: RepositorioTrabajosMemoria) -> None:
    trabajo = await _servicio(repositorio, PublicadorFalso()).crear("PRUEBA", {}, ANA)

    respuesta = respuesta_creado(trabajo)

    assert respuesta.status_code == 202
    assert respuesta.headers["Location"] == f"/api/ia/v1/trabajos/{trabajo.id}"


async def test_tipo_no_registrado_es_error_de_programacion(
    repositorio: RepositorioTrabajosMemoria,
) -> None:
    with pytest.raises(KeyError):
        await _servicio(repositorio, PublicadorFalso()).crear("OTRO", {}, ANA)
    assert repositorio.documentos == {}


async def test_publicacion_fallida_deja_el_trabajo_fallido_y_responde_503(
    repositorio: RepositorioTrabajosMemoria,
) -> None:
    with pytest.raises(ErrorAplicacion) as error:
        await _servicio(repositorio, PublicadorFalso(falla=True)).crear("PRUEBA", {}, ANA)

    assert error.value.estado_http == 503
    assert error.value.codigo == "DEPENDENCIA_NO_DISPONIBLE"
    (documento,) = repositorio.documentos.values()
    assert documento["estado"] == "FALLIDO"
    assert documento["error"]["codigo"] == "COLA_NO_DISPONIBLE"
    assert documento["fechaExpiracion"] == AHORA + timedelta(days=30)


async def test_mongodb_caido_al_crear_responde_503(
    repositorio: RepositorioTrabajosMemoria,
) -> None:
    repositorio.fallas["guardar_nuevo"] = 1
    publicador = PublicadorFalso()

    with pytest.raises(ErrorAplicacion) as error:
        await _servicio(repositorio, publicador).crear("PRUEBA", {}, ANA)

    assert error.value.estado_http == 503
    assert publicador.publicados == []


async def test_obtener_para_el_solicitante(repositorio: RepositorioTrabajosMemoria) -> None:
    servicio = _servicio(repositorio, PublicadorFalso())
    trabajo = await servicio.crear("PRUEBA", {}, ANA)

    assert (await servicio.obtener_para(trabajo.id.upper(), ANA)).id == trabajo.id


@pytest.mark.parametrize("caso", ["ajeno", "inexistente", "id-invalido"])
async def test_obtener_para_ajeno_inexistente_o_invalido_es_404(
    repositorio: RepositorioTrabajosMemoria, caso: str
) -> None:
    servicio = _servicio(repositorio, PublicadorFalso())
    trabajo = await servicio.crear("PRUEBA", {}, ANA)
    pedido = {"ajeno": trabajo.id, "inexistente": str(uuid.uuid4()), "id-invalido": "abc"}[caso]

    with pytest.raises(ErrorAplicacion) as error:
        await servicio.obtener_para(pedido, LUIS if caso == "ajeno" else ANA)

    assert error.value.estado_http == 404
    assert error.value.codigo == "TRABAJO_NO_ENCONTRADO"


async def test_obtener_con_mongodb_caido_responde_503(
    repositorio: RepositorioTrabajosMemoria,
) -> None:
    repositorio.fallas["obtener"] = 1

    with pytest.raises(ErrorAplicacion) as error:
        await _servicio(repositorio, PublicadorFalso()).obtener_para(str(uuid.uuid4()), ANA)

    assert error.value.estado_http == 503
