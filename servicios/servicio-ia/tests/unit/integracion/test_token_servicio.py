"""spec-base.md, Historia 4, escenarios 1 y 2, y casos borde."""

import asyncio
from urllib.parse import parse_qs

import httpx
import pytest

from app.integracion.errores import ErrorServicioRemoto, TipoErrorRemoto
from app.integracion.token_servicio import TokenCuentaServicio


class Reloj:
    def __init__(self) -> None:
        self.ahora = 0.0

    def __call__(self) -> float:
        return self.ahora


class KeycloakTokens:
    def __init__(self) -> None:
        self.pedidos: list[dict[str, list[str]]] = []
        self.estado = 200

    async def responder(self, solicitud: httpx.Request) -> httpx.Response:
        self.pedidos.append(parse_qs(solicitud.content.decode()))
        await asyncio.sleep(0.01)
        if self.estado != 200:
            return httpx.Response(self.estado, json={"error": "invalid_client"})
        return httpx.Response(
            200, json={"access_token": f"token-{len(self.pedidos)}", "expires_in": 300}
        )


@pytest.fixture
def keycloak() -> KeycloakTokens:
    return KeycloakTokens()


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def token(keycloak: KeycloakTokens, reloj: Reloj) -> TokenCuentaServicio:
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(keycloak.responder))
    return TokenCuentaServicio(cliente, "http://kc/token", "servicio-ia", "s3creto", reloj=reloj)


async def test_pide_con_client_credentials_y_guarda_en_cache(
    token: TokenCuentaServicio, keycloak: KeycloakTokens
) -> None:
    assert await token.obtener() == "token-1"
    assert await token.obtener() == "token-1"

    assert len(keycloak.pedidos) == 1
    assert keycloak.pedidos[0] == {
        "grant_type": ["client_credentials"],
        "client_id": ["servicio-ia"],
        "client_secret": ["s3creto"],
    }


async def test_renueva_cuando_faltan_menos_de_30_segundos(
    token: TokenCuentaServicio, reloj: Reloj
) -> None:
    await token.obtener()
    reloj.ahora = 269
    assert await token.obtener() == "token-1"
    reloj.ahora = 271
    assert await token.obtener() == "token-2"


async def test_invalidar_fuerza_un_token_nuevo(token: TokenCuentaServicio) -> None:
    await token.obtener()
    token.invalidar()

    assert await token.obtener() == "token-2"


async def test_consultas_simultaneas_piden_un_solo_token(
    token: TokenCuentaServicio, keycloak: KeycloakTokens
) -> None:
    resultados = await asyncio.gather(*(token.obtener() for _ in range(10)))

    assert set(resultados) == {"token-1"}
    assert len(keycloak.pedidos) == 1


async def test_keycloak_rechaza_o_cae_y_el_secreto_no_aparece(
    token: TokenCuentaServicio, keycloak: KeycloakTokens, caplog: pytest.LogCaptureFixture
) -> None:
    keycloak.estado = 401

    with pytest.raises(ErrorServicioRemoto) as error:
        await token.obtener()

    assert error.value.servicio == "keycloak"
    assert error.value.tipo is TipoErrorRemoto.NO_DISPONIBLE
    assert "s3creto" not in caplog.text
