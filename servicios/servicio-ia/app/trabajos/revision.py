"""Revisión periódica que cierra los trabajos atascados (spec-trabajos.md 2.10)."""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import datetime

from app.integracion.errores import ErrorInfraestructura
from app.integracion.repositorio_trabajos import RepositorioTrabajos
from app.trabajos.consumidor import registrar_falla_de_tarea
from app.trabajos.esquemas import Trabajo
from app.trabajos.estados import (
    ESPERA_MAXIMA_EN_COLA,
    EstadoTrabajo,
    calcular_fecha_expiracion,
    esta_vencido,
)
from app.trabajos.servicio import ahora_utc, error_trabajo

INTERVALO_SEGUNDOS = 60.0
_logger = logging.getLogger("app.trabajos.revision")


async def revisar_vencidos(
    repositorio: RepositorioTrabajos, ahora: datetime, dias_retencion: int
) -> int:
    """Marca `FALLIDO` los trabajos vencidos y devuelve cuántos cerró esta vuelta."""
    cerrados = 0
    for documento in await repositorio.listar_vencidos(ahora, ahora - ESPERA_MAXIMA_EN_COLA):
        trabajo = Trabajo.desde_documento(documento)
        if not esta_vencido(trabajo.estado, trabajo.fecha_creacion, trabajo.fecha_limite, ahora):
            continue
        codigo = (
            "TIEMPO_AGOTADO"
            if trabajo.estado is EstadoTrabajo.PROCESANDO
            else "TRABAJO_NO_PROCESADO"
        )
        cerrado = await repositorio.cambiar_estado(
            trabajo.id,
            trabajo.estado,
            EstadoTrabajo.FALLIDO,
            {
                "error": error_trabajo(codigo),
                "fechaFin": ahora,
                "fechaExpiracion": calcular_fecha_expiracion(ahora, dias_retencion),
            },
        )
        if cerrado:
            cerrados += 1
            _logger.warning(
                "Trabajo atascado cerrado", extra={"idTrabajo": trabajo.id, "codigo": codigo}
            )
    return cerrados


class RevisionPeriodica:
    def __init__(
        self,
        repositorio: RepositorioTrabajos,
        dias_retencion: int,
        reloj: Callable[[], datetime] = ahora_utc,
        intervalo: float = INTERVALO_SEGUNDOS,
    ) -> None:
        self._repositorio = repositorio
        self._dias_retencion = dias_retencion
        self._reloj = reloj
        self._intervalo = intervalo
        self._tarea: asyncio.Task[None] | None = None

    def iniciar(self) -> None:
        self._tarea = asyncio.create_task(self._ciclo(), name="revision-trabajos")
        self._tarea.add_done_callback(registrar_falla_de_tarea)

    async def _ciclo(self) -> None:
        while True:
            try:
                await revisar_vencidos(self._repositorio, self._reloj(), self._dias_retencion)
            except ErrorInfraestructura as error:
                _logger.warning("Revisión de trabajos fallida", extra={"motivo": str(error)})
            await asyncio.sleep(self._intervalo)

    async def detener(self) -> None:
        if self._tarea is not None and not self._tarea.done():
            self._tarea.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._tarea
