"""Solicitud de reporte: texto libre o el plan ya armado (spec-reportes.md 2.10)."""

from typing import Annotated

from pydantic import StringConstraints

from app.comun.esquemas import ModeloBase, ModeloEntrada
from app.reportes.plan import FormatoReporte, PlanReporte

TextoSolicitud = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)
]


class SolicitudTexto(ModeloEntrada):
    texto: TextoSolicitud
    formatos: list[FormatoReporte] | None = None


# Se envía `texto` o el plan (con `tablas`), nunca ambos: los dos esquemas rechazan los campos
# del otro.
SolicitudReporte = SolicitudTexto | PlanReporte


class CampoCatalogo(ModeloBase):
    nombre: str
    etiqueta: str
    tipo: str
    valores: list[str]
    por_defecto: bool
    operadores: list[str]


class FuenteCatalogo(ModeloBase):
    nombre: str
    descripcion: str
    de_una_campania: bool
    campos: list[CampoCatalogo]
