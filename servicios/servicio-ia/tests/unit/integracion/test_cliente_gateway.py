"""spec-base.md, Historia 4, escenarios 1 y 3 a 6, y 8."""

from collections.abc import Callable

import httpx
import pytest

from app.comun.correlacion import id_correlacion_actual
from app.integracion.errores import ErrorServicioRemoto, TipoErrorRemoto
from app.integracion.gateway import ClienteGateway
from app.integracion.token_servicio import TokenCuentaServicio

Manejador = Callable[[httpx.Request], httpx.Response]


class TokenFijo(TokenCuentaServicio):
    def __init__(self) -> None:
        self.emitidos = 0
        self.invalidaciones = 0

    async def obtener(self) -> str:
        self.emitidos += 1
        return f"token-{self.emitidos}"

    def invalidar(self) -> None:
        self.invalidaciones += 1


def _cliente(manejador: Manejador, token: TokenCuentaServicio | None = None) -> ClienteGateway:
    http = httpx.AsyncClient(transport=httpx.MockTransport(manejador))
    return ClienteGateway(http, "http://gateway.prueba/", token or TokenFijo(), tiempo_limite=1.0)


async def test_envia_token_correlacion_y_parametros() -> None:
    recibidas: list[httpx.Request] = []

    def manejador(solicitud: httpx.Request) -> httpx.Response:
        recibidas.append(solicitud)
        return httpx.Response(200, json={"items": []})

    contexto = id_correlacion_actual.set("corr-1")
    try:
        datos = await _cliente(manejador).obtener(
            "/api/gestion/v1/campanias/historicos", {"tamanio": "500"}
        )
    finally:
        id_correlacion_actual.reset(contexto)

    assert datos == {"items": []}
    solicitud = recibidas[0]
    assert solicitud.method == "GET"
    assert (
        str(solicitud.url)
        == "http://gateway.prueba/api/gestion/v1/campanias/historicos?tamanio=500"
    )
    assert solicitud.headers["Authorization"] == "Bearer token-1"
    assert solicitud.headers["X-Correlation-Id"] == "corr-1"
    assert solicitud.headers["Accept"] == "application/json"


async def test_401_renueva_el_token_y_repite_una_vez() -> None:
    token = TokenFijo()
    respuestas = iter([httpx.Response(401), httpx.Response(200, json={"ok": True})])

    datos = await _cliente(lambda _: next(respuestas), token).obtener("/api/inventario/v1/insumos")

    assert datos == {"ok": True}
    assert token.invalidaciones == 1
    assert token.emitidos == 2


async def test_401_repetido_es_no_disponible() -> None:
    with pytest.raises(ErrorServicioRemoto) as error:
        await _cliente(lambda _: httpx.Response(401)).obtener("/api/inventario/v1/insumos")

    assert error.value.tipo is TipoErrorRemoto.NO_DISPONIBLE
    assert error.value.servicio == "servicio-inventario"


async def test_404_con_codigo_del_servicio_es_no_encontrado() -> None:
    def manejador(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"codigo": "CAMPANIA_NO_ENCONTRADA"})

    with pytest.raises(ErrorServicioRemoto) as error:
        await _cliente(manejador).obtener("/api/gestion/v1/campanias/x")

    assert error.value.tipo is TipoErrorRemoto.NO_ENCONTRADO
    assert error.value.codigo == "CAMPANIA_NO_ENCONTRADA"


@pytest.mark.parametrize(
    "respuesta",
    [
        httpx.Response(404, json={"codigo": "RUTA_NO_ENCONTRADA"}),
        httpx.Response(404, json={"codigo": "RECURSO_NO_ENCONTRADO"}),
        httpx.Response(404, text="no es json"),
        httpx.Response(503, json={"codigo": "SERVICIO_NO_DISPONIBLE"}),
        httpx.Response(504, json={"codigo": "TIEMPO_AGOTADO"}),
        httpx.Response(500),
        httpx.Response(200, text="<html>no es json</html>"),
    ],
    ids=["ruta-gateway", "ruta-servicio", "404-sin-json", "503", "504", "500", "2xx-no-json"],
)
async def test_respuestas_que_son_no_disponible(respuesta: httpx.Response) -> None:
    with pytest.raises(ErrorServicioRemoto) as error:
        await _cliente(lambda _: respuesta).obtener("/api/gestion/v1/campanias")

    assert error.value.tipo is TipoErrorRemoto.NO_DISPONIBLE


@pytest.mark.parametrize("excepcion", [httpx.ConnectError, httpx.ReadTimeout])
async def test_conexion_fallida_o_tiempo_agotado_es_no_disponible(
    excepcion: type[httpx.TransportError],
) -> None:
    def manejador(solicitud: httpx.Request) -> httpx.Response:
        raise excepcion("falla", request=solicitud)

    with pytest.raises(ErrorServicioRemoto) as error:
        await _cliente(manejador).obtener("/api/operaciones/v1/labores")

    assert error.value.tipo is TipoErrorRemoto.NO_DISPONIBLE
    assert error.value.servicio == "servicio-operaciones"


@pytest.mark.parametrize("estado", [400, 403, 409, 422])
async def test_rechazos_se_informan_y_registran(
    estado: int, caplog: pytest.LogCaptureFixture
) -> None:
    def manejador(_: httpx.Request) -> httpx.Response:
        return httpx.Response(estado, json={"codigo": "SIN_PERMISO"})

    with pytest.raises(ErrorServicioRemoto) as error:
        await _cliente(manejador).obtener("/api/gestion/v1/campanias")

    assert error.value.tipo is TipoErrorRemoto.RECHAZADO
    assert error.value.codigo == "SIN_PERMISO"
    assert any(r.levelname == "ERROR" for r in caplog.records)


async def test_ruta_fuera_del_formato_es_error_de_programacion() -> None:
    with pytest.raises(ValueError):
        await _cliente(lambda _: httpx.Response(200)).obtener("/campanias")


def test_el_cliente_solo_tiene_lecturas() -> None:
    publicos = {n for n in dir(ClienteGateway) if not n.startswith("_")}

    assert publicos == {"obtener"}
