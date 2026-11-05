"""Datos de servicio-gestion para predicción y análisis (spec-prediccion.md 2.7).

`DatosAgricolas` es el borde externo que los tests reemplazan (constitución §3); el adaptador
consulta servicio-gestion a través del gateway con la cuenta de servicio (solo lectura).
"""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from app.integracion.gateway import ClienteGateway

GESTION = "/api/gestion/v1"
TAMANIO_PAGINA_HISTORICOS = 500


@dataclass(frozen=True)
class CampaniaPrediccion:
    id: str
    nombre_cultivo: str
    estado: str
    superficie_hectareas: Decimal
    subtotales_por_categoria: dict[str, Decimal]
    rendimiento_real: Decimal | None


@dataclass(frozen=True)
class Historicos:
    items: list[dict[str, Any]]
    total: int


class DatosAgricolas(Protocol):
    async def campania_para_prediccion(self, id_campania: str) -> CampaniaPrediccion: ...

    async def historicos(self, filtros: Mapping[str, str], maximo: int) -> Historicos: ...


def _decimal(valor: Any) -> Decimal | None:
    return Decimal(str(valor)) if valor is not None else None


class DatosAgricolasGateway:
    def __init__(self, gateway: ClienteGateway) -> None:
        self._gateway = gateway

    async def campania_para_prediccion(self, id_campania: str) -> CampaniaPrediccion:
        """Campaña, nombre del cultivo, subtotales de costos y, si terminó, su rendimiento real.

        Un `404` del servicio llega como `ErrorServicioRemoto` de tipo `NO_ENCONTRADO`.
        """
        campania = await self._gateway.obtener(f"{GESTION}/campanias/{id_campania}")
        consultas = [
            self._gateway.obtener(f"{GESTION}/cultivos/{campania['idCultivo']}"),
            self._gateway.obtener(f"{GESTION}/campanias/{id_campania}/costos", {"tamanio": "1"}),
        ]
        if campania["estado"] == "FINALIZADA":
            consultas.append(
                self._gateway.obtener(f"{GESTION}/campanias/{id_campania}/indicadores")
            )
        cultivo, costos, *indicadores = await asyncio.gather(*consultas)
        rendimiento_real = (
            _decimal(indicadores[0].get("rendimientoPorHectarea")) if indicadores else None
        )
        superficie = _decimal(campania["superficieHectareas"])
        assert superficie is not None
        return CampaniaPrediccion(
            id=str(campania["id"]),
            nombre_cultivo=str(cultivo["nombre"]),
            estado=str(campania["estado"]),
            superficie_hectareas=superficie,
            subtotales_por_categoria={
                c: Decimal(str(v)) for c, v in costos["subtotalesPorCategoria"].items()
            },
            rendimiento_real=rendimiento_real,
        )

    async def historicos(self, filtros: Mapping[str, str], maximo: int) -> Historicos:
        """Hasta `maximo` campañas finalizadas, las más recientes primero, y el total real."""
        items: list[dict[str, Any]] = []
        pagina = 0
        total = 0
        while len(items) < maximo:
            respuesta = await self._gateway.obtener(
                f"{GESTION}/campanias/historicos",
                {**filtros, "pagina": str(pagina), "tamanio": str(TAMANIO_PAGINA_HISTORICOS)},
            )
            items += respuesta["items"]
            total = int(respuesta["total"])
            pagina += 1
            if pagina * TAMANIO_PAGINA_HISTORICOS >= total:
                break
        return Historicos(items=items[:maximo], total=total)
