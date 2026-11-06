"""Obtención de cada fuente de datos con las herramientas MCP (spec-reportes.md 2.5).

Devuelve filas con los campos del catálogo y los valores tal cual. Los nombres de otras
entidades se completan buscando por ID (no es un cálculo). Algunos filtros simples se pasan a
la herramienta para traer menos datos; `plan.aplicar` los vuelve a aplicar igual.
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import mcp.types as tipos_mcp

from app.agentes.nodos import SesionMcp
from app.reportes.catalogo import ESTADOS_LABOR, FUENTES
from app.reportes.plan import Operador, TablaPlan, convertidor

MAXIMO = 500
_PREFIJO_ERROR_MCP = re.compile(r"^Error executing tool \S+: ")


class ErrorFuente(Exception):
    """Una herramienta falló: un reporte con datos incompletos no sirve (2.7, `recopilar`)."""


@dataclass
class DatosFuente:
    filas: list[dict[str, Any]]
    total_origen: int
    recortado: bool = False


async def llamar(sesion: SesionMcp, herramienta: str, argumentos: dict[str, Any]) -> Any:
    resultado = await sesion.call_tool(herramienta, argumentos)
    if resultado.is_error:
        texto = "".join(b.text for b in resultado.content if isinstance(b, tipos_mcp.TextContent))
        raise ErrorFuente(_PREFIJO_ERROR_MCP.sub("", texto))
    return resultado.structured_content or {}


class Nombres:
    """Diccionarios `id → nombre` que se piden una sola vez por reporte."""

    def __init__(self, sesion: SesionMcp) -> None:
        self._sesion = sesion
        self._cache: dict[str, Any] = {}

    async def _items(self, herramienta: str) -> list[dict[str, Any]]:
        if herramienta not in self._cache:
            datos = await llamar(self._sesion, herramienta, {"maximo": MAXIMO})
            self._cache[herramienta] = datos.get("items") or []
        items: list[dict[str, Any]] = self._cache[herramienta]
        return items

    async def parcelas(self) -> dict[str, str]:
        return {p["id"]: p["nombre"] for p in await self._items("listar_parcelas")}

    async def cultivos(self) -> dict[str, str]:
        return {c["id"]: c["nombre"] for c in await self._items("listar_cultivos")}

    async def campanias(self) -> dict[str, str]:
        return {c["id"]: c["nombre"] for c in await self._items("listar_campanias")}

    async def insumos(self) -> dict[str, tuple[str, str]]:
        return {
            i["idInsumo"]: (i["nombre"], i.get("unidad") or "")
            for i in await self._items("consultar_estado_inventario")
        }


def _filtro_igual(tabla: TablaPlan, campo: str) -> Any:
    """El valor de un filtro `igual` sobre `campo`, convertido a su tipo, o `None`."""
    fuente = FUENTES[tabla.fuente]
    definicion = fuente.campo(campo)
    for filtro in tabla.filtros:
        if filtro.campo == campo and filtro.operador is Operador.IGUAL and definicion:
            return convertidor(definicion)(filtro.valor)
    return None


def _datos(listado: dict[str, Any], filas: list[dict[str, Any]]) -> DatosFuente:
    return DatosFuente(
        filas, int(listado.get("total") or len(filas)), bool(listado.get("truncado"))
    )


async def _parcelas(s: SesionMcp, t: TablaPlan, _: str | None, n: Nombres) -> DatosFuente:
    datos = await llamar(s, "listar_parcelas", {"maximo": MAXIMO})
    return _datos(datos, list(datos.get("items") or []))


async def _cultivos(s: SesionMcp, t: TablaPlan, _: str | None, n: Nombres) -> DatosFuente:
    datos = await llamar(s, "listar_cultivos", {"maximo": MAXIMO})
    return _datos(datos, list(datos.get("items") or []))


async def _campanias(s: SesionMcp, t: TablaPlan, _: str | None, n: Nombres) -> DatosFuente:
    argumentos: dict[str, Any] = {"maximo": MAXIMO}
    if (estado := _filtro_igual(t, "estado")) is not None:
        argumentos["estado"] = estado
    datos = await llamar(s, "listar_campanias", argumentos)
    parcelas, cultivos = await n.parcelas(), await n.cultivos()
    filas = [
        {
            **c,
            "nombreParcela": parcelas.get(c.get("idParcela") or ""),
            "nombreCultivo": cultivos.get(c.get("idCultivo") or ""),
        }
        for c in datos.get("items") or []
    ]
    return _datos(datos, filas)


_CATEGORIAS_HISTORICO = {
    "INSUMO": "costoInsumo",
    "MANO_DE_OBRA": "costoManoDeObra",
    "MAQUINARIA": "costoMaquinaria",
    "OTRO": "costoOtro",
}


async def _finalizadas(s: SesionMcp, t: TablaPlan, _: str | None, n: Nombres) -> DatosFuente:
    datos = await llamar(s, "listar_historicos", {"maximo": MAXIMO})
    campanias = await n.campanias()
    filas = []
    for h in datos.get("items") or []:
        por_categoria = h.get("costosPorCategoria") or {}
        filas.append(
            {
                **h,
                "nombreCampania": campanias.get(h.get("idCampania") or ""),
                **{campo: por_categoria.get(cat) for cat, campo in _CATEGORIAS_HISTORICO.items()},
            }
        )
    return _datos(datos, filas)


async def _costos(s: SesionMcp, t: TablaPlan, id_campania: str | None, n: Nombres) -> DatosFuente:
    datos = await llamar(
        s, "obtener_costos_campania", {"idCampania": id_campania, "maximo": MAXIMO}
    )
    return _datos(datos, list(datos.get("items") or []))


async def _subtotales(
    s: SesionMcp, t: TablaPlan, id_campania: str | None, n: Nombres
) -> DatosFuente:
    datos = await llamar(s, "obtener_costos_campania", {"idCampania": id_campania, "maximo": 1})
    subtotales = datos.get("subtotalesPorCategoria") or {}
    filas = [{"categoria": c, "subtotal": v} for c, v in subtotales.items()]
    return DatosFuente(filas, len(filas))


async def _indicadores(
    s: SesionMcp, t: TablaPlan, id_campania: str | None, n: Nombres
) -> DatosFuente:
    campania = await llamar(s, "obtener_campania", {"idCampania": id_campania})
    indicadores = await llamar(s, "obtener_indicadores_campania", {"idCampania": id_campania})
    fila = {
        "nombre": campania.get("nombre"),
        "estado": campania.get("estado"),
        **{
            k: indicadores.get(k)
            for k in (
                "superficieHectareas",
                "produccion",
                "costoTotal",
                "rendimientoPorHectarea",
                "costoPorHectarea",
                "definitivo",
            )
        },
    }
    return DatosFuente([fila], 1)


async def _inventario(s: SesionMcp, t: TablaPlan, _: str | None, n: Nombres) -> DatosFuente:
    argumentos: dict[str, Any] = {"maximo": MAXIMO}
    if _filtro_igual(t, "stockBajo") is True:
        argumentos["soloStockBajo"] = True
    if (categoria := _filtro_igual(t, "categoria")) is not None:
        argumentos["categoria"] = categoria
    datos = await llamar(s, "consultar_estado_inventario", argumentos)
    return _datos(datos, list(datos.get("items") or []))


async def _labores(s: SesionMcp, t: TablaPlan, _: str | None, n: Nombres) -> DatosFuente:
    """`servicio-operaciones` exige campaña o estado: sin campaña, se recorre cada estado."""
    estado = _filtro_igual(t, "estado")
    items: list[dict[str, Any]] = []
    recortado = False
    for valor in [estado] if estado else ESTADOS_LABOR:
        datos = await llamar(s, "listar_labores", {"estado": valor, "maximo": MAXIMO})
        items.extend(datos.get("items") or [])
        recortado = recortado or bool(datos.get("truncado"))
    campanias, parcelas, insumos = await n.campanias(), await n.parcelas(), await n.insumos()
    filas = []
    for labor in items:
        consumos = []
        for consumo in labor.get("insumos") or []:
            nombre, unidad = insumos.get(consumo.get("idInsumo"), ("Insumo desconocido", ""))
            consumos.append(f"{nombre}: {consumo.get('cantidad')} {unidad}".strip())
        filas.append(
            {
                **labor,
                "nombreCampania": campanias.get(labor.get("idCampania") or ""),
                "nombreParcela": parcelas.get(labor.get("idParcela") or ""),
                "insumos": "; ".join(consumos) or None,
            }
        )
    return DatosFuente(filas, len(filas), recortado)


async def _incidencias(s: SesionMcp, t: TablaPlan, _: str | None, n: Nombres) -> DatosFuente:
    """`servicio-operaciones` exige parcela o campaña: sin campaña, se recorre cada parcela."""
    parcelas = await n.parcelas()
    tipo = _filtro_igual(t, "tipo")
    items: list[dict[str, Any]] = []
    recortado = False
    for id_parcela in parcelas:
        argumentos: dict[str, Any] = {"idParcela": id_parcela, "maximo": MAXIMO}
        if tipo:
            argumentos["tipo"] = tipo
        datos = await llamar(s, "listar_incidencias", argumentos)
        items.extend(datos.get("items") or [])
        recortado = recortado or bool(datos.get("truncado"))
    campanias = await n.campanias()
    filas = []
    for incidencia in items:
        clasificacion = incidencia.get("clasificacion") or {}
        filas.append(
            {
                **incidencia,
                "nombreParcela": parcelas.get(incidencia.get("idParcela") or ""),
                "nombreCampania": campanias.get(incidencia.get("idCampania") or ""),
                "clasificacion": clasificacion.get("categoria"),
                "confianzaClasificacion": clasificacion.get("confianza"),
            }
        )
    return DatosFuente(filas, len(filas), recortado)


Obtener = Callable[[SesionMcp, TablaPlan, str | None, Nombres], Awaitable[DatosFuente]]
OBTENER: dict[str, Obtener] = {
    "PARCELAS": _parcelas,
    "CULTIVOS": _cultivos,
    "CAMPANIAS": _campanias,
    "CAMPANIAS_FINALIZADAS": _finalizadas,
    "COSTOS_CAMPANIA": _costos,
    "SUBTOTALES_CAMPANIA": _subtotales,
    "INDICADORES_CAMPANIA": _indicadores,
    "INVENTARIO": _inventario,
    "LABORES": _labores,
    "INCIDENCIAS": _incidencias,
}


async def obtener(
    sesion: SesionMcp, tabla: TablaPlan, id_campania: str | None, nombres: Nombres
) -> DatosFuente:
    return await OBTENER[tabla.fuente](sesion, tabla, id_campania, nombres)
