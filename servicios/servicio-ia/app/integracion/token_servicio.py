"""Token de la cuenta de servicio `servicio-ia` (client credentials contra Keycloak)."""

import asyncio
import logging
import time
from collections.abc import Callable

import httpx

from app.integracion.errores import ErrorServicioRemoto, TipoErrorRemoto

_MARGEN_RENOVACION = 30.0
_logger = logging.getLogger("app.integracion.token")


class TokenCuentaServicio:
    def __init__(
        self,
        cliente: httpx.AsyncClient,
        url_token: str,
        client_id: str,
        client_secret: str,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cliente = cliente
        self._url = url_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._reloj = reloj
        self._token: str | None = None
        self._vence_en = 0.0
        self._candado = asyncio.Lock()

    def _vigente(self) -> bool:
        return self._token is not None and self._vence_en - self._reloj() > _MARGEN_RENOVACION

    async def obtener(self) -> str:
        if self._vigente():
            assert self._token is not None
            return self._token
        async with self._candado:
            if self._vigente():  # otra tarea lo renovó mientras se esperaba
                assert self._token is not None
                return self._token
            self._token, self._vence_en = await self._pedir()
            return self._token

    def invalidar(self) -> None:
        self._token = None
        self._vence_en = 0.0

    async def _pedir(self) -> tuple[str, float]:
        try:
            respuesta = await self._cliente.post(
                self._url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=5.0,
            )
            respuesta.raise_for_status()
            datos = respuesta.json()
            token = str(datos["access_token"])
            duracion = float(datos.get("expires_in", 60))
        except (httpx.HTTPError, ValueError, KeyError) as error:
            _logger.warning(
                "No se pudo obtener el token de la cuenta de servicio",
                extra={"motivo": type(error).__name__},
            )
            raise ErrorServicioRemoto("keycloak", TipoErrorRemoto.NO_DISPONIBLE) from None
        return token, self._reloj() + duracion
