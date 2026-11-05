"""Trabajo asíncrono y sus respuestas (spec-trabajos.md 1.3 y 2.11)."""

from datetime import datetime
from typing import Any

from app.comun.esquemas import FechaHoraUtc, ModeloBase
from app.trabajos.estados import EstadoTrabajo


class ErrorTrabajo(ModeloBase):
    codigo: str
    mensaje: str


class Trabajo(ModeloBase):
    id: str
    tipo: str
    estado: EstadoTrabajo
    id_solicitante: str
    id_correlacion: str | None
    parametros: dict[str, Any]
    resultado: dict[str, Any] | None = None
    error: ErrorTrabajo | None = None
    fecha_creacion: datetime
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    fecha_limite: datetime | None = None
    fecha_expiracion: datetime | None = None

    def a_documento(self) -> dict[str, Any]:
        """Documento de Firestore en camelCase, con fechas como `datetime`."""
        documento = self.model_dump(by_alias=True, mode="python")
        documento["estado"] = self.estado.value
        return documento

    @classmethod
    def desde_documento(cls, documento: dict[str, Any]) -> "Trabajo":
        return cls.model_validate(documento)


class RespuestaTrabajo(ModeloBase):
    id_trabajo: str
    tipo: str
    estado: EstadoTrabajo
    fecha_creacion: FechaHoraUtc
    fecha_inicio: FechaHoraUtc | None
    fecha_fin: FechaHoraUtc | None
    id_correlacion: str | None
    resultado: dict[str, Any] | None
    error: ErrorTrabajo | None

    @classmethod
    def desde(cls, trabajo: Trabajo) -> "RespuestaTrabajo":
        return cls(
            id_trabajo=trabajo.id,
            tipo=trabajo.tipo,
            estado=trabajo.estado,
            fecha_creacion=trabajo.fecha_creacion,
            fecha_inicio=trabajo.fecha_inicio,
            fecha_fin=trabajo.fecha_fin,
            id_correlacion=trabajo.id_correlacion,
            resultado=trabajo.resultado if trabajo.estado is EstadoTrabajo.COMPLETADO else None,
            error=trabajo.error if trabajo.estado is EstadoTrabajo.FALLIDO else None,
        )


class RespuestaTrabajoCreado(ModeloBase):
    id_trabajo: str
    estado: EstadoTrabajo
    fecha_creacion: FechaHoraUtc
