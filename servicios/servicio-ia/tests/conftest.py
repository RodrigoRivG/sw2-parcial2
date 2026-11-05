"""Aplicación de prueba, claves RSA locales y emisor de tokens (spec-base.md 2.7 y 2.12).

Las rutas `/api/ia/v1/prueba/...` existen solo en los tests.
"""

import time
import uuid
from collections.abc import Callable, Iterator
from decimal import Decimal
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.comun.errores import respuestas_error
from app.comun.esquemas import DecimalTexto, ModeloBase, ModeloEntrada
from app.comun.seguridad import (
    UsuarioAutenticado,
    proveedor_claves,
    requerir_roles,
    router_protegido,
)
from app.config import Configuracion
from app.integracion.errores import ErrorServicioRemoto, TipoErrorRemoto
from app.main import crear_app

EMISOR = "http://localhost:8180/realms/agro"
AUDIENCIA = "servicio-ia"
KID = "clave-de-prueba"

_clave_privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_otra_clave_privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def configuracion_de_prueba() -> Configuracion:
    return Configuracion(
        keycloak_issuer=EMISOR,
        keycloak_jwks_uri="http://keycloak.prueba/certs",
        keycloak_audience=AUDIENCIA,
        keycloak_token_url="http://keycloak.prueba/token",
        keycloak_client_id="servicio-ia",
        keycloak_client_secret=SecretStr("secreto-de-prueba"),
        api_gateway_url="http://gateway.prueba",
        nivel_log="DEBUG",
    )


def jwk_publico(clave: rsa.RSAPrivateKey = _clave_privada, kid: str = KID) -> dict[str, Any]:
    datos: dict[str, Any] = jwt.algorithms.RSAAlgorithm.to_jwk(clave.public_key(), as_dict=True)
    return {**datos, "kid": kid, "use": "sig", "alg": "RS256"}


def emitir_token(
    roles: list[str] | None = None,
    *,
    sub: str = "usuario-1",
    emisor: str = EMISOR,
    audiencia: str | list[str] = AUDIENCIA,
    vence_en: int = 300,
    clave: rsa.RSAPrivateKey = _clave_privada,
    kid: str = KID,
    nombre: str | None = "Ana Quispe",
) -> str:
    ahora = int(time.time())
    datos: dict[str, Any] = {
        "sub": sub,
        "iss": emisor,
        "aud": audiencia,
        "iat": ahora,
        "exp": ahora + vence_en,
        "jti": str(uuid.uuid4()),
        "realm_access": {"roles": roles or []},
        "preferred_username": "ana.quispe",
    }
    if nombre:
        datos["name"] = nombre
    return jwt.encode(datos, clave, algorithm="RS256", headers={"kid": kid})


def autorizacion(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class ProveedorClavesLocal:
    """Reemplaza al JWKS de Keycloak con la clave local de los tests."""

    def __init__(self) -> None:
        self._claves = {KID: jwt.PyJWK(jwk_publico())}

    async def clave(self, kid: str) -> jwt.PyJWK | None:
        return self._claves.get(kid)


class CuerpoPrueba(ModeloEntrada):
    nombre: str
    monto_total: DecimalTexto


class RespuestaUsuario(ModeloBase):
    id: str
    nombre: str
    roles: list[str]


def _router_de_prueba() -> Any:
    router = router_protegido(tags=["prueba"])
    errores = respuestas_error(400, 401, 403, 500)

    @router.get("/prueba/gerencia", responses=errores)
    async def solo_gerencia(
        usuario: UsuarioAutenticado = Depends(requerir_roles("gerencia")),
    ) -> RespuestaUsuario:
        return RespuestaUsuario(id=usuario.id, nombre=usuario.nombre, roles=sorted(usuario.roles))

    @router.post("/prueba/validacion", responses=errores)
    async def validacion(cuerpo: CuerpoPrueba) -> dict[str, str]:
        monto: Decimal = cuerpo.monto_total
        return {"montoTotal": format(monto, "f")}

    @router.get("/prueba/error-interno", responses=errores)
    async def error_interno() -> None:
        raise RuntimeError("detalle que no debe salir en la respuesta")

    @router.get("/prueba/error-remoto/{tipo}", responses=errores)
    async def error_remoto(tipo: TipoErrorRemoto) -> None:
        raise ErrorServicioRemoto("servicio-gestion", tipo, "CAMPANIA_NO_ENCONTRADA", 404)

    return router


@pytest.fixture
def crear_cliente() -> Iterator[Callable[..., TestClient]]:
    clientes: list[TestClient] = []

    def crear(ajustar: Callable[[FastAPI], None] | None = None) -> TestClient:
        app = crear_app(configuracion_de_prueba())
        app.include_router(_router_de_prueba())
        app.dependency_overrides[proveedor_claves] = ProveedorClavesLocal
        if ajustar:
            ajustar(app)
        cliente = TestClient(app, raise_server_exceptions=False)
        cliente.__enter__()
        clientes.append(cliente)
        return cliente

    yield crear
    for cliente in clientes:
        cliente.__exit__(None, None, None)


@pytest.fixture
def cliente(crear_cliente: Callable[..., TestClient]) -> TestClient:
    return crear_cliente()


@pytest.fixture
def otra_clave_privada() -> rsa.RSAPrivateKey:
    return _otra_clave_privada
