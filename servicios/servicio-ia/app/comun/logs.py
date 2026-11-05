"""Logs JSON de una línea por registro, con el idCorrelacion del contexto (README D-10)."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.comun.correlacion import id_correlacion_actual

_ATRIBUTOS_ESTANDAR = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()) | {
    "message",
    "asctime",
    "taskName",
    "color_message",  # copia con colores ANSI que agrega uvicorn
}


class FormateadorJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        datos: dict[str, Any] = {
            "fecha": datetime.fromtimestamp(record.created, UTC).isoformat().replace("+00:00", "Z"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
            "idCorrelacion": id_correlacion_actual.get(),
        }
        for clave, valor in record.__dict__.items():
            if clave not in _ATRIBUTOS_ESTANDAR and not clave.startswith("_"):
                datos[clave] = valor
        if record.exc_info:
            datos["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False, default=str)


def configurar_logs(nivel: str = "INFO") -> None:
    """Un único handler JSON en la salida estándar; uvicorn propaga al logger raíz.

    El log de acceso de uvicorn se apaga: lo reemplaza el de `MiddlewareCorrelacion`.
    """
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormateadorJson())
    raiz = logging.getLogger()
    raiz.handlers = [manejador]
    raiz.setLevel(nivel.upper())
    for nombre in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(nombre)
        logger.handlers = []
        logger.propagate = True
    acceso_uvicorn = logging.getLogger("uvicorn.access")
    acceso_uvicorn.handlers = []
    acceso_uvicorn.propagate = False
