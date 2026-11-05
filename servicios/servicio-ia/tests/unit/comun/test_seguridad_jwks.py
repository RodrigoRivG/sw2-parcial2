"""spec-base.md, Historia 2, escenarios 5 y 6."""

import httpx
import pytest

from app.comun.errores import ErrorAplicacion
from app.comun.seguridad import ProveedorClavesJwks
from tests.conftest import KID, jwk_publico


class Reloj:
    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora


class Keycloak:
    """JWKS simulado que cuenta las descargas y se puede apagar."""

    def __init__(self) -> None:
        self.descargas = 0
        self.caido = False
        self.claves = [jwk_publico()]

    def responder(self, solicitud: httpx.Request) -> httpx.Response:
        self.descargas += 1
        if self.caido:
            raise httpx.ConnectError("sin conexión", request=solicitud)
        return httpx.Response(200, json={"keys": self.claves})


@pytest.fixture
def keycloak() -> Keycloak:
    return Keycloak()


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def proveedor(keycloak: Keycloak, reloj: Reloj) -> ProveedorClavesJwks:
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(keycloak.responder))
    return ProveedorClavesJwks(cliente, "http://keycloak.prueba/certs", reloj=reloj)


async def test_usa_la_cache_durante_diez_minutos(
    proveedor: ProveedorClavesJwks, keycloak: Keycloak, reloj: Reloj
) -> None:
    assert await proveedor.clave(KID) is not None
    reloj.ahora += 599
    assert await proveedor.clave(KID) is not None
    assert keycloak.descargas == 1

    reloj.ahora += 2
    await proveedor.clave(KID)
    assert keycloak.descargas == 2


async def test_kid_nuevo_descarga_de_nuevo_como_maximo_cada_30_segundos(
    proveedor: ProveedorClavesJwks, keycloak: Keycloak, reloj: Reloj
) -> None:
    await proveedor.clave(KID)
    keycloak.claves.append(jwk_publico(kid="rotada"))

    reloj.ahora += 10
    assert await proveedor.clave("rotada") is None  # todavía no pasaron 30 s
    reloj.ahora += 25
    assert await proveedor.clave("rotada") is not None
    reloj.ahora += 5
    assert await proveedor.clave("otra-desconocida") is None
    assert keycloak.descargas == 2


async def test_sin_claves_y_keycloak_caido_responde_503(
    proveedor: ProveedorClavesJwks, keycloak: Keycloak
) -> None:
    keycloak.caido = True

    with pytest.raises(ErrorAplicacion) as error:
        await proveedor.clave(KID)

    assert error.value.estado_http == 503
    assert error.value.codigo == "AUTENTICACION_NO_DISPONIBLE"


async def test_claves_vencidas_se_siguen_usando_si_keycloak_cae(
    proveedor: ProveedorClavesJwks, keycloak: Keycloak, reloj: Reloj
) -> None:
    await proveedor.clave(KID)
    keycloak.caido = True
    reloj.ahora += 700

    assert await proveedor.clave(KID) is not None
