"""Formato común de errores (constitución §11) y su traducción a HTTP."""

import json
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic.alias_generators import to_camel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.comun.correlacion import id_correlacion_actual
from app.comun.esquemas import ModeloBase
from app.integracion.errores import ErrorInfraestructura, ErrorServicioRemoto, TipoErrorRemoto

_logger = logging.getLogger("app.errores")

MENSAJES = {
    "DATOS_INVALIDOS": "Los datos enviados no son válidos.",
    "NO_AUTENTICADO": "Debe iniciar sesión para continuar.",
    "SIN_PERMISO": "No tiene permiso para realizar esta operación.",
    "RECURSO_NO_ENCONTRADO": "El recurso solicitado no existe.",
    "METODO_NO_PERMITIDO": "El método no está permitido para este recurso.",
    "ERROR_INTERNO": "Ocurrió un error inesperado.",
    "AUTENTICACION_NO_DISPONIBLE": (
        "No se pudo verificar la sesión. Intente nuevamente en unos minutos."
    ),
    "DEPENDENCIA_NO_DISPONIBLE": (
        "No se pudieron obtener los datos necesarios. Intente nuevamente en unos minutos."
    ),
}

_CODIGO_POR_ESTADO = {
    400: "DATOS_INVALIDOS",
    401: "NO_AUTENTICADO",
    403: "SIN_PERMISO",
    404: "RECURSO_NO_ENCONTRADO",
    405: "METODO_NO_PERMITIDO",
}

_MENSAJES_VALIDACION = {
    "missing": "Campo obligatorio.",
    "extra_forbidden": "Campo no permitido.",
    "string_type": "Debe ser texto.",
    "uuid_parsing": "Debe ser un UUID.",
    "uuid_type": "Debe ser un UUID.",
    "int_parsing": "Debe ser un número entero.",
    "int_type": "Debe ser un número entero.",
    "bool_parsing": "Debe ser verdadero o falso.",
    "bool_type": "Debe ser verdadero o falso.",
    "date_from_datetime_parsing": "Debe ser una fecha AAAA-MM-DD.",
    "date_parsing": "Debe ser una fecha AAAA-MM-DD.",
    "datetime_parsing": "Debe ser una fecha y hora ISO 8601.",
    "json_invalid": "El cuerpo no es un JSON válido.",
    "model_attributes_type": "Debe ser un objeto JSON.",
    "dict_type": "Debe ser un objeto JSON.",
    "list_type": "Debe ser una lista.",
}


class DetalleError(ModeloBase):
    campo: str
    mensaje: str


class RespuestaError(ModeloBase):
    codigo: str
    mensaje: str
    detalles: list[DetalleError]
    id_correlacion: str | None


class ErrorAplicacion(Exception):
    """Error esperado de un módulo, con su código HTTP y su código estable."""

    def __init__(
        self,
        estado_http: int,
        codigo: str,
        mensaje: str | None = None,
        detalles: list[DetalleError] | None = None,
    ) -> None:
        self.estado_http = estado_http
        self.codigo = codigo
        self.mensaje = mensaje or MENSAJES.get(codigo, MENSAJES["ERROR_INTERNO"])
        self.detalles = detalles or []
        super().__init__(f"{codigo}: {self.mensaje}")


def cuerpo_error(
    codigo: str, mensaje: str, detalles: list[DetalleError] | None = None
) -> dict[str, Any]:
    return RespuestaError(
        codigo=codigo,
        mensaje=mensaje,
        detalles=detalles or [],
        id_correlacion=id_correlacion_actual.get(),
    ).model_dump(mode="json", by_alias=True)


def respuesta_error(
    estado_http: int,
    codigo: str,
    mensaje: str | None = None,
    detalles: list[DetalleError] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=estado_http,
        content=cuerpo_error(codigo, mensaje or MENSAJES.get(codigo, ""), detalles),
    )


def error_interno_asgi() -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """500 común para el middleware de correlación (errores no controlados)."""
    cuerpo = json.dumps(cuerpo_error("ERROR_INTERNO", MENSAJES["ERROR_INTERNO"])).encode()
    return 500, [(b"content-type", b"application/json")], cuerpo


def _campo(ubicacion: tuple[int | str, ...], tipo: str) -> str:
    if tipo == "json_invalid":
        return "cuerpo"
    partes = (
        list(ubicacion[1:])
        if ubicacion and ubicacion[0] in ("body", "query", "path", "header")
        else list(ubicacion)
    )
    if not partes:
        return "cuerpo"
    return ".".join(to_camel(p) if isinstance(p, str) else str(p) for p in partes)


def _mensaje_validacion(error: dict[str, Any]) -> str:
    tipo = error.get("type", "")
    if tipo == "value_error":
        return str(error.get("msg", "")).removeprefix("Value error, ")
    if tipo in ("enum", "literal_error"):
        esperado = error.get("ctx", {}).get("expected", "")
        return f"Valor no permitido. Valores admitidos: {esperado}."
    if tipo in ("string_too_short", "string_too_long"):
        ctx = error.get("ctx", {})
        limite = ctx.get("min_length", ctx.get("max_length"))
        return f"Longitud no permitida (límite: {limite})."
    if tipo in ("greater_than", "greater_than_equal", "less_than", "less_than_equal"):
        return "Valor fuera del rango permitido."
    return _MENSAJES_VALIDACION.get(tipo, str(error.get("msg", "Valor inválido.")))


async def _validacion(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    detalles = [
        DetalleError(
            campo=_campo(tuple(e.get("loc", ())), e.get("type", "")), mensaje=_mensaje_validacion(e)
        )
        for e in error.errors()
    ]
    return respuesta_error(400, "DATOS_INVALIDOS", detalles=detalles)


async def _aplicacion(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ErrorAplicacion)
    return respuesta_error(error.estado_http, error.codigo, error.mensaje, error.detalles)


async def _infraestructura(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ErrorInfraestructura)
    _logger.warning("Infraestructura no disponible", extra={"componente": error.componente})
    return respuesta_error(503, "DEPENDENCIA_NO_DISPONIBLE")


async def _servicio_remoto(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ErrorServicioRemoto)
    if error.tipo is TipoErrorRemoto.NO_DISPONIBLE:
        return respuesta_error(503, "DEPENDENCIA_NO_DISPONIBLE")
    _logger.error(
        "Error de un servicio remoto no manejado",
        extra={"servicio": error.servicio, "tipo": error.tipo.value, "codigoRemoto": error.codigo},
    )
    return respuesta_error(500, "ERROR_INTERNO")


async def _http(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, StarletteHTTPException)
    codigo = _CODIGO_POR_ESTADO.get(error.status_code)
    if codigo is None:
        return respuesta_error(500, "ERROR_INTERNO")
    return respuesta_error(error.status_code, codigo)


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validacion)
    app.add_exception_handler(ErrorAplicacion, _aplicacion)
    app.add_exception_handler(ErrorServicioRemoto, _servicio_remoto)
    app.add_exception_handler(ErrorInfraestructura, _infraestructura)
    app.add_exception_handler(StarletteHTTPException, _http)


def respuestas_error(*estados: int) -> dict[int | str, dict[str, Any]]:
    """Documentación OpenAPI de las respuestas de error de una ruta (README D-14)."""
    return {estado: {"model": RespuestaError, "description": "Error"} for estado in estados}
