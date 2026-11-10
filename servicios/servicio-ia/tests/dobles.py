"""Dobles de prueba de los bordes de infraestructura (README D-12)."""

import copy
from datetime import datetime
from typing import Any

from app.integracion.errores import ErrorInfraestructura


class RepositorioTrabajosMemoria:
    """Mismo contrato que `RepositorioTrabajosMongo`, en memoria.

    `fallas[operacion] = n` hace que las próximas `n` llamadas a esa operación fallen.
    """

    def __init__(self) -> None:
        self.documentos: dict[str, dict[str, Any]] = {}
        self.fallas: dict[str, int] = {}
        self.llamadas: list[str] = []

    def _quizas_fallar(self, operacion: str) -> None:
        self.llamadas.append(operacion)
        if self.fallas.get(operacion, 0) > 0:
            self.fallas[operacion] -= 1
            raise ErrorInfraestructura("mongodb", "falla simulada")

    async def guardar_nuevo(self, documento: dict[str, Any]) -> None:
        self._quizas_fallar("guardar_nuevo")
        if documento["id"] in self.documentos:
            raise ValueError("ya existe")
        self.documentos[documento["id"]] = copy.deepcopy(documento)

    async def obtener(self, id_trabajo: str) -> dict[str, Any] | None:
        self._quizas_fallar("obtener")
        documento = self.documentos.get(id_trabajo)
        return copy.deepcopy(documento) if documento else None

    async def cambiar_estado(
        self, id_trabajo: str, desde: str, hacia: str, cambios: dict[str, Any]
    ) -> bool:
        self._quizas_fallar("cambiar_estado")
        documento = self.documentos.get(id_trabajo)
        if documento is None or documento["estado"] != desde:
            return False
        documento.update(copy.deepcopy(cambios))
        documento["estado"] = hacia
        return True

    async def listar_vencidos(
        self, ahora: datetime, creados_antes: datetime, limite: int = 100
    ) -> list[dict[str, Any]]:
        self._quizas_fallar("listar_vencidos")
        vencidos = [
            d
            for d in self.documentos.values()
            if (d["estado"] == "PROCESANDO" and d.get("fechaLimite") and d["fechaLimite"] < ahora)
            or (d["estado"] == "EN_COLA" and d["fechaCreacion"] < creados_antes)
        ]
        return copy.deepcopy(vencidos[:limite])


class PublicadorFalso:
    """Reemplaza a `ConexionRabbitMq` en los tests unitarios."""

    cola_trabajos = "pruebas.servicio-ia.trabajos"

    def __init__(self, falla: bool = False) -> None:
        self.falla = falla
        self.publicados: list[tuple[str, dict[str, Any]]] = []

    async def publicar(self, cola: str, sobre: dict[str, Any]) -> None:
        if self.falla:
            raise ErrorInfraestructura("rabbitmq", "falla simulada")
        self.publicados.append((cola, sobre))
