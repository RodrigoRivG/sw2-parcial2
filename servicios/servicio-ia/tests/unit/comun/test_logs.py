import json
import logging

from app.comun.correlacion import id_correlacion_actual, normalizar_id
from app.comun.logs import FormateadorJson


def _registro(mensaje: str, **extra: object) -> logging.LogRecord:
    registro = logging.LogRecord("app.prueba", logging.INFO, __file__, 1, mensaje, None, None)
    for clave, valor in extra.items():
        setattr(registro, clave, valor)
    return registro


def test_una_linea_json_con_id_de_correlacion_del_contexto_y_campos_extra() -> None:
    token = id_correlacion_actual.set("abc-123")
    try:
        linea = FormateadorJson().format(_registro("hola ñandú", duracionMs=12.5))
    finally:
        id_correlacion_actual.reset(token)

    assert "\n" not in linea
    datos = json.loads(linea)
    assert datos["mensaje"] == "hola ñandú"
    assert datos["nivel"] == "INFO"
    assert datos["logger"] == "app.prueba"
    assert datos["idCorrelacion"] == "abc-123"
    assert datos["duracionMs"] == 12.5
    assert datos["fecha"].endswith("Z")


def test_sin_contexto_el_id_es_nulo() -> None:
    datos = json.loads(FormateadorJson().format(_registro("x")))

    assert datos["idCorrelacion"] is None


def test_la_traza_de_una_excepcion_va_en_su_campo() -> None:
    try:
        raise ValueError("falla")
    except ValueError:
        import sys

        registro = logging.LogRecord(
            "app", logging.ERROR, __file__, 1, "error", None, sys.exc_info()
        )

    datos = json.loads(FormateadorJson().format(registro))

    assert "ValueError: falla" in datos["excepcion"]


def test_normalizar_id_acepta_validos_y_reemplaza_invalidos() -> None:
    assert normalizar_id("abc-123") == "abc-123"
    assert normalizar_id(None) != normalizar_id(None)
    assert len(normalizar_id("a" * 65)) == 36
    assert len(normalizar_id("con espacio")) == 36
