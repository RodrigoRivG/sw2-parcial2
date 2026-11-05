"""Cliente de solo lectura hacia los microservicios por el API Gateway (README D-08, RN-14)."""

import logging
import re
import time
from collections.abc import Mapping
from typing import Any, NoReturn

import httpx
from fastapi import Request

from app.comun.correlacion import ENCABEZADO, id_correlacion_actual
from app.integracion.errores import ErrorServicioRemoto, TipoErrorRemoto
from app.integracion.token_servicio import TokenCuentaServicio

_PATRON_RUTA = re.compile(r"^/api/([a-z]+)/v\d+/")
_CODIGOS_DE_RUTA = {None, "RUTA_NO_ENCONTRADA", "RECURSO_NO_ENCONTRADO"}
_logger = logging.getLogger("app.integracion.gateway")


class ClienteGateway:
    """Solo expone consultas GET: no hay forma de escribir en otro servicio."""

    def __init__(
        self,
        cliente: httpx.AsyncClient,
        url_base: str,
        token: TokenCuentaServicio,
        tiempo_limite: float = 5.0,
    ) -> None:
        self._cliente = cliente
        self._url_base = url_base.rstrip("/")
        self._token = token
        self._tiempo_limite = tiempo_limite

    async def obtener(
        self,
        ruta: str,
        parametros: Mapping[str, str] | None = None,
        tiempo_limite: float | None = None,
    ) -> Any:
        coincidencia = _PATRON_RUTA.match(ruta)
        if coincidencia is None:
            raise ValueError(f"Ruta fuera del formato /api/<servicio>/v<n>/...: {ruta}")
        servicio = f"servicio-{coincidencia.group(1)}"

        for intento in (1, 2):
            respuesta = await self._enviar(servicio, ruta, parametros, tiempo_limite)
            if respuesta.status_code == 401 and intento == 1:
                self._token.invalidar()
                continue
            return self._interpretar(servicio, ruta, respuesta)
        raise AssertionError("inalcanzable")  # pragma: no cover

    async def _enviar(
        self,
        servicio: str,
        ruta: str,
        parametros: Mapping[str, str] | None,
        tiempo_limite: float | None,
    ) -> httpx.Response:
        token = await self._token.obtener()
        encabezados = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        id_correlacion = id_correlacion_actual.get()
        if id_correlacion:
            encabezados[ENCABEZADO] = id_correlacion
        inicio = time.perf_counter()
        try:
            respuesta = await self._cliente.get(
                self._url_base + ruta,
                params=dict(parametros or {}),
                headers=encabezados,
                timeout=tiempo_limite or self._tiempo_limite,
            )
        except httpx.HTTPError as error:
            _logger.warning(
                "Servicio no disponible",
                extra={"servicio": servicio, "ruta": ruta, "motivo": type(error).__name__},
            )
            raise ErrorServicioRemoto(servicio, TipoErrorRemoto.NO_DISPONIBLE) from None
        _logger.debug(
            "Consulta a servicio",
            extra={
                "servicio": servicio,
                "ruta": ruta,
                "estado": respuesta.status_code,
                "duracionMs": round((time.perf_counter() - inicio) * 1000, 1),
            },
        )
        return respuesta

    @staticmethod
    def _codigo(respuesta: httpx.Response) -> str | None:
        try:
            datos = respuesta.json()
        except ValueError:
            return None
        codigo = datos.get("codigo") if isinstance(datos, dict) else None
        return str(codigo) if codigo else None

    def _interpretar(self, servicio: str, ruta: str, respuesta: httpx.Response) -> Any:
        estado = respuesta.status_code
        if 200 <= estado < 300:
            try:
                return respuesta.json()
            except ValueError:
                self._fallo(servicio, ruta, TipoErrorRemoto.NO_DISPONIBLE, None, estado)
        codigo = self._codigo(respuesta)
        if estado == 401:
            _logger.error(
                "La cuenta de servicio fue rechazada dos veces", extra={"servicio": servicio}
            )
            self._fallo(servicio, ruta, TipoErrorRemoto.NO_DISPONIBLE, codigo, estado)
        if estado == 404:
            tipo = (
                TipoErrorRemoto.NO_DISPONIBLE
                if codigo in _CODIGOS_DE_RUTA
                else TipoErrorRemoto.NO_ENCONTRADO
            )
            self._fallo(servicio, ruta, tipo, codigo, estado)
        if 400 <= estado < 500:
            self._fallo(servicio, ruta, TipoErrorRemoto.RECHAZADO, codigo, estado)
        self._fallo(servicio, ruta, TipoErrorRemoto.NO_DISPONIBLE, codigo, estado)

    @staticmethod
    def _fallo(
        servicio: str, ruta: str, tipo: TipoErrorRemoto, codigo: str | None, estado: int
    ) -> NoReturn:
        extra = {"servicio": servicio, "ruta": ruta, "estado": estado, "codigoRemoto": codigo}
        if tipo is TipoErrorRemoto.RECHAZADO:
            _logger.error("Consulta rechazada por el servicio", extra=extra)
        elif tipo is TipoErrorRemoto.NO_DISPONIBLE:
            _logger.warning("Servicio no disponible", extra=extra)
        raise ErrorServicioRemoto(servicio, tipo, codigo, estado)


def cliente_gateway(request: Request) -> ClienteGateway:
    """Dependencia de FastAPI para los módulos que consultan otros servicios."""
    gateway: ClienteGateway = request.app.state.cliente_gateway
    return gateway
