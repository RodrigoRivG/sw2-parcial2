"""Solicitud de consulta a los agentes (spec-agentes.md 2.7)."""

from typing import Annotated

from pydantic import StringConstraints

from app.comun.esquemas import ModeloEntrada

Pregunta = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]


class SolicitudConsulta(ModeloEntrada):
    pregunta: Pregunta
