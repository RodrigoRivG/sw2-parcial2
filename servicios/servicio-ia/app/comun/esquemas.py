"""Tipos comunes de los esquemas JSON (README D-03, D-04 y D-06)."""

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, PlainSerializer
from pydantic.alias_generators import to_camel

_PATRON_DECIMAL = re.compile(r"^-?\d{1,15}(\.\d{1,6})?$")


class ModeloBase(BaseModel):
    """Esquema con campos en camelCase en JSON y snake_case en Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ModeloEntrada(ModeloBase):
    """Esquema de entrada: además rechaza campos desconocidos."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


def _validar_decimal_texto(valor: Any) -> Decimal:
    if isinstance(valor, Decimal):
        return valor
    if not isinstance(valor, str) or not _PATRON_DECIMAL.match(valor):
        raise ValueError('Debe enviarse como texto decimal, por ejemplo "820.50".')
    return Decimal(valor)


DecimalTexto = Annotated[
    Decimal,
    BeforeValidator(_validar_decimal_texto),
    PlainSerializer(lambda valor: format(valor, "f"), return_type=str),
]
"""Decimal que viaja en JSON como texto con punto decimal (nunca como número)."""


def _exigir_zona(valor: datetime) -> datetime:
    if valor.tzinfo is None or valor.utcoffset() is None:
        raise ValueError(
            "La fecha y hora debe incluir la zona horaria (por ejemplo, terminar en Z)."
        )
    return valor.astimezone(UTC)


def _serializar_utc(valor: datetime) -> str:
    return valor.astimezone(UTC).isoformat().replace("+00:00", "Z")


FechaHoraUtc = Annotated[
    datetime,
    AfterValidator(_exigir_zona),
    PlainSerializer(_serializar_utc, return_type=str),
]
"""Fecha y hora en UTC; se serializa en ISO 8601 con sufijo Z."""
