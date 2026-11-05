from datetime import timedelta
from typing import Any

import pytest

from app.trabajos.esquemas import Trabajo
from app.trabajos.registro import DefinicionTipo, RegistroTipos


async def _manejador(trabajo: Trabajo) -> dict[str, Any]:
    return {}


def test_registrar_y_obtener() -> None:
    registro = RegistroTipos()
    definicion = DefinicionTipo("REPORTE", _manejador, timedelta(minutes=5))

    registro.registrar(definicion)

    assert "REPORTE" in registro
    assert registro.obtener("REPORTE") is definicion


def test_tipo_duplicado_falla() -> None:
    registro = RegistroTipos()
    registro.registrar(DefinicionTipo("REPORTE", _manejador, timedelta(minutes=5)))

    with pytest.raises(ValueError):
        registro.registrar(DefinicionTipo("REPORTE", _manejador, timedelta(minutes=1)))


def test_tipo_no_registrado_falla() -> None:
    with pytest.raises(KeyError):
        RegistroTipos().obtener("DESCONOCIDO")
