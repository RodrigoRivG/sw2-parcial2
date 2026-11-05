"""Errores al consultar servicios externos (Keycloak y microservicios a través del gateway)."""

from enum import StrEnum


class TipoErrorRemoto(StrEnum):
    NO_DISPONIBLE = "NO_DISPONIBLE"
    NO_ENCONTRADO = "NO_ENCONTRADO"
    RECHAZADO = "RECHAZADO"


class ErrorServicioRemoto(Exception):
    def __init__(
        self,
        servicio: str,
        tipo: TipoErrorRemoto,
        codigo: str | None = None,
        estado_http: int | None = None,
    ) -> None:
        self.servicio = servicio
        self.tipo = tipo
        self.codigo = codigo
        self.estado_http = estado_http
        super().__init__(f"{servicio}: {tipo.value} ({codigo or estado_http or 'sin respuesta'})")
