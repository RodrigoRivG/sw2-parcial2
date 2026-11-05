from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.comun.esquemas import DecimalTexto, FechaHoraUtc, ModeloBase, ModeloEntrada


class Entrada(ModeloEntrada):
    monto_total: DecimalTexto
    fecha_registro: FechaHoraUtc | None = None


class Salida(ModeloBase):
    monto_total: DecimalTexto
    fecha_registro: FechaHoraUtc


def test_decimal_como_texto_se_convierte_a_decimal() -> None:
    entrada = Entrada.model_validate({"montoTotal": "820.50"})

    assert entrada.monto_total == Decimal("820.50")


@pytest.mark.parametrize("valor", [820.5, 820, True, "820,50", "1e3", "", "abc"])
def test_decimal_rechaza_numero_json_y_formatos_invalidos(valor: object) -> None:
    with pytest.raises(ValidationError) as error:
        Entrada.model_validate({"montoTotal": valor})

    assert "texto decimal" in str(error.value)


def test_salida_en_camel_case_con_decimal_como_texto_y_fecha_utc_con_z() -> None:
    hora_bolivia = timezone(timedelta(hours=-4))
    salida = Salida(
        monto_total=Decimal("820.50"),
        fecha_registro=datetime(2026, 11, 4, 10, 0, tzinfo=hora_bolivia),
    )

    assert salida.model_dump(mode="json", by_alias=True) == {
        "montoTotal": "820.50",
        "fechaRegistro": "2026-11-04T14:00:00Z",
    }


def test_fecha_sin_zona_horaria_se_rechaza() -> None:
    with pytest.raises(ValidationError):
        Entrada.model_validate({"montoTotal": "1.00", "fechaRegistro": "2026-11-04T10:00:00"})


def test_fecha_con_zona_se_lleva_a_utc() -> None:
    entrada = Entrada.model_validate(
        {"montoTotal": "1.00", "fechaRegistro": "2026-11-04T10:00:00-04:00"}
    )

    assert entrada.fecha_registro == datetime(2026, 11, 4, 14, 0, tzinfo=UTC)


def test_entrada_rechaza_campos_desconocidos() -> None:
    with pytest.raises(ValidationError):
        Entrada.model_validate({"montoTotal": "1.00", "otro": 1})
