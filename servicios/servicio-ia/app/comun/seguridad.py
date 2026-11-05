"""Validación del JWT de Keycloak y verificación de roles (constitución §9, RNF-02, RN-16)."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.comun.errores import ErrorAplicacion

PREFIJO_API = "/api/ia/v1"
_DURACION_CACHE = 600.0
_INTERVALO_MINIMO_DESCARGA = 30.0

_logger = logging.getLogger("app.seguridad")
_esquema_bearer = HTTPBearer(auto_error=False, description="Token JWT emitido por Keycloak")


class ProveedorClavesJwks:
    """Claves públicas de Keycloak por `kid`, en caché durante 10 minutos."""

    def __init__(
        self,
        cliente: httpx.AsyncClient,
        uri: str,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cliente = cliente
        self._uri = uri
        self._reloj = reloj
        self._claves: dict[str, jwt.PyJWK] = {}
        self._descargado_en: float | None = None
        self._ultimo_intento: float | None = None
        self._candado = asyncio.Lock()

    async def clave(self, kid: str) -> jwt.PyJWK | None:
        ahora = self._reloj()
        vencidas = self._descargado_en is None or ahora - self._descargado_en > _DURACION_CACHE
        desconocida = kid not in self._claves
        if vencidas or (desconocida and self._puede_reintentar(ahora)):
            await self._descargar()
        if not self._claves:
            raise ErrorAplicacion(503, "AUTENTICACION_NO_DISPONIBLE")
        return self._claves.get(kid)

    def _puede_reintentar(self, ahora: float) -> bool:
        return (
            self._ultimo_intento is None
            or ahora - self._ultimo_intento >= _INTERVALO_MINIMO_DESCARGA
        )

    async def _descargar(self) -> None:
        async with self._candado:
            ahora = self._reloj()
            if self._ultimo_intento is not None and ahora - self._ultimo_intento < 1.0:
                return  # otra tarea acaba de descargar
            self._ultimo_intento = ahora
            try:
                respuesta = await self._cliente.get(self._uri, timeout=3.0)
                respuesta.raise_for_status()
                conjunto = jwt.PyJWKSet.from_dict(respuesta.json())
            except (httpx.HTTPError, ValueError, jwt.PyJWTError) as error:
                if self._claves:
                    _logger.warning(
                        "No se pudo renovar el JWKS; se usan las claves en caché",
                        extra={"motivo": str(error)},
                    )
                else:
                    _logger.error("No se pudo descargar el JWKS", extra={"motivo": str(error)})
                return
            self._claves = {c.key_id: c for c in conjunto.keys if c.key_id}
            self._descargado_en = ahora


@dataclass(frozen=True)
class UsuarioAutenticado:
    id: str
    nombre: str
    roles: frozenset[str]

    def tiene_alguno(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))


def proveedor_claves(request: Request) -> ProveedorClavesJwks:
    proveedor: ProveedorClavesJwks = request.app.state.proveedor_claves
    return proveedor


async def usuario_actual(
    request: Request,
    credenciales: HTTPAuthorizationCredentials | None = Depends(_esquema_bearer),
    proveedor: ProveedorClavesJwks = Depends(proveedor_claves),
) -> UsuarioAutenticado:
    if credenciales is None:
        raise ErrorAplicacion(401, "NO_AUTENTICADO")
    configuracion = request.app.state.configuracion
    token = credenciales.credentials
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except jwt.PyJWTError:
        raise ErrorAplicacion(401, "NO_AUTENTICADO") from None
    if not kid:
        raise ErrorAplicacion(401, "NO_AUTENTICADO")
    clave = await proveedor.clave(str(kid))
    if clave is None:
        raise ErrorAplicacion(401, "NO_AUTENTICADO")
    try:
        datos: dict[str, Any] = jwt.decode(
            token,
            clave.key,
            algorithms=["RS256"],
            audience=configuracion.keycloak_audience,
            issuer=configuracion.keycloak_issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError:
        raise ErrorAplicacion(401, "NO_AUTENTICADO") from None

    roles = datos.get("realm_access", {}).get("roles", [])
    usuario = UsuarioAutenticado(
        id=str(datos["sub"]),
        nombre=str(datos.get("name") or datos.get("preferred_username") or datos.get("azp") or ""),
        roles=frozenset(r for r in roles if isinstance(r, str)),
    )
    request.state.sub = usuario.id
    return usuario


def requerir_roles(*roles: str) -> Callable[..., Awaitable[UsuarioAutenticado]]:
    """Dependencia que exige al menos uno de los roles; si no, 403 SIN_PERMISO."""

    async def verificar(
        usuario: UsuarioAutenticado = Depends(usuario_actual),
    ) -> UsuarioAutenticado:
        if not usuario.tiene_alguno(*roles):
            raise ErrorAplicacion(403, "SIN_PERMISO")
        return usuario

    return verificar


def router_protegido(**opciones: Any) -> APIRouter:
    """Router con el prefijo de la API que exige token en todas sus rutas."""
    return APIRouter(prefix=PREFIJO_API, dependencies=[Depends(usuario_actual)], **opciones)
