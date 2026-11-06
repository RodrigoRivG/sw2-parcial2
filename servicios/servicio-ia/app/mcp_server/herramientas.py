"""Herramientas MCP de solo lectura sobre los microservicios (spec-agentes.md 2.3, RN-14).

Cada herramienta consulta un endpoint por el gateway con la cuenta de servicio, reduce la
respuesta a los campos útiles y recorta los listados. No redacta ni calcula cifras nuevas.
Los textos libres se recortan y viajan como datos dentro del JSON, nunca como instrucciones.
"""

from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal, Protocol
from uuid import UUID

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BeforeValidator, Field

from app.integracion.errores import ErrorServicioRemoto, TipoErrorRemoto

GESTION = "/api/gestion/v1"
INVENTARIO = "/api/inventario/v1"
OPERACIONES = "/api/operaciones/v1"
MAXIMO_POR_DEFECTO = 50
MAXIMO_PERMITIDO = 500
LARGO_TEXTO = 200
TAMANIO_PAGINA = 100  # máximo de gestión, inventario y operaciones
TAMANIO_HISTORICOS = 500


def _mayusculas(valor: Any) -> Any:
    """Los modelos pequeños escriben "fitosanitario" o "en curso": se acepta igual."""
    return valor.strip().upper().replace(" ", "_") if isinstance(valor, str) else valor


_Mayusculas = BeforeValidator(_mayusculas)
EstadoCampania = Annotated[Literal["PLANIFICADA", "EN_CURSO", "FINALIZADA"], _Mayusculas]
CategoriaInsumo = Annotated[Literal["SEMILLA", "FERTILIZANTE", "FITOSANITARIO"], _Mayusculas]
EstadoLabor = Annotated[
    Literal["PROGRAMADA", "PENDIENTE", "CONFIRMADA", "RECHAZADA", "PENDIENTE_REVISION"],
    _Mayusculas,
]
TipoIncidencia = Annotated[Literal["PLAGA", "ENFERMEDAD", "DANIO", "OTRO"], _Mayusculas]
OrdenHistoricos = Literal["costoPorHectarea", "rendimientoPorHectarea", "fechaFinalizacion"]

IdCampania = Annotated[UUID, Field(description="ID (UUID) de la campaña")]
Maximo = Annotated[
    int,
    Field(ge=1, le=MAXIMO_PERMITIDO, description="Cantidad máxima de elementos (1 a 500)"),
]
Fecha = Annotated[date | None, Field(description="Fecha AAAA-MM-DD")]

_NO_ENCONTRADO = {
    "CAMPANIA_NO_ENCONTRADA": "la campaña no existe",
    "INSUMO_NO_ENCONTRADO": "el insumo no existe",
}


class Lector(Protocol):
    """Lo que las herramientas necesitan del cliente del gateway: solo `GET`."""

    async def obtener(self, ruta: str, parametros: Mapping[str, str] | None = None) -> Any: ...


def _texto(valor: Any) -> Any:
    if isinstance(valor, str) and len(valor) > LARGO_TEXTO:
        return valor[: LARGO_TEXTO - 1] + "…"
    return valor


def _campos(origen: Mapping[str, Any], nombres: tuple[str, ...]) -> dict[str, Any]:
    return {nombre: _texto(origen.get(nombre)) for nombre in nombres}


def _listado(items: list[dict[str, Any]], total: int, truncado: bool) -> dict[str, Any]:
    return {"items": items, "total": total, "truncado": truncado}


def _filtros(**valores: Any) -> dict[str, str]:
    resultado = {}
    for nombre, valor in valores.items():
        if valor is None:
            continue
        if isinstance(valor, bool):
            resultado[nombre] = "true" if valor else "false"
        elif isinstance(valor, date):
            resultado[nombre] = valor.isoformat()
        else:
            resultado[nombre] = str(valor)
    return resultado


def _mensaje(error: ErrorServicioRemoto) -> str:
    if error.tipo is TipoErrorRemoto.NO_ENCONTRADO:
        codigo = error.codigo or "NO_ENCONTRADO"
        return f"{codigo}: {_NO_ENCONTRADO.get(codigo, 'el recurso no existe')}"
    if error.tipo is TipoErrorRemoto.RECHAZADO:
        return f"{error.codigo or 'RECHAZADO'}: {error.servicio} rechazó la consulta"
    return f"{error.servicio} no disponible"


def _decimal(valor: Any) -> Decimal | None:
    try:
        return Decimal(str(valor)) if valor not in (None, "") else None
    except InvalidOperation:
        return None


# Campos que se conservan de cada recurso (sin versión, huellas ni fechas técnicas)
PARCELA = ("id", "nombre", "superficieHectareas", "ubicacion", "descripcion")
CULTIVO = ("id", "nombre", "variedad", "unidadMedida", "descripcion")
CAMPANIA = (
    "id",
    "nombre",
    "idParcela",
    "idCultivo",
    "fechaInicio",
    "fechaFin",
    "superficieHectareas",
    "estado",
    "fechaFinalizacion",
)
COSTO = ("categoria", "monto", "fecha", "descripcion", "origen")
HISTORICO = (
    "idCampania",
    "nombreParcela",
    "nombreCultivo",
    "variedad",
    "superficieHectareas",
    "fechaInicio",
    "fechaFinalizacion",
    "duracionDias",
    "produccion",
    "costoTotal",
    "costosPorCategoria",
    "rendimientoPorHectarea",
    "costoPorHectarea",
    "motivosNoDisponible",
)
ESTADO_INSUMO = (
    "idInsumo",
    "nombre",
    "categoria",
    "unidad",
    "stock",
    "nivelMinimo",
    "stockBajo",
    "fechaUltimaAlerta",
)
INSUMO = (
    "id",
    "nombre",
    "categoria",
    "unidad",
    "stock",
    "nivelMinimo",
    "costoUnitario",
    "descripcion",
    "stockBajo",
)
LABOR = (
    "id",
    "tipoLabor",
    "idParcela",
    "idCampania",
    "estado",
    "fechaProgramada",
    "fechaEjecucion",
    "observaciones",
    "insumos",
)
INCIDENCIA = ("id", "tipo", "descripcion", "fechaObservacion", "idParcela", "idCampania")


def _labor(labor: Mapping[str, Any]) -> dict[str, Any]:
    reducida = _campos(labor, LABOR)
    reducida["responsable"] = (labor.get("responsable") or {}).get("nombre")
    return reducida


def _incidencia(incidencia: Mapping[str, Any]) -> dict[str, Any]:
    reducida = _campos(incidencia, INCIDENCIA)
    reducida["registradaPor"] = (incidencia.get("registradaPor") or {}).get("nombre")
    clasificacion = incidencia.get("clasificacion")
    reducida["clasificacion"] = (
        {k: clasificacion.get(k) for k in ("categoria", "confianza", "origen")}
        if isinstance(clasificacion, Mapping)
        else None
    )
    return reducida


class HerramientasLectura:
    """Las 11 herramientas de 2.3. Los métodos públicos son las herramientas registradas."""

    def __init__(self, lector: Lector) -> None:
        self._lector = lector

    async def _obtener(self, ruta: str, parametros: Mapping[str, str] | None = None) -> Any:
        try:
            return await self._lector.obtener(ruta, parametros)
        except ErrorServicioRemoto as error:
            raise ToolError(_mensaje(error)) from None

    async def _paginas(
        self, ruta: str, filtros: Mapping[str, str], maximo: int
    ) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
        """Páginas `{items, total}` con `pagina` desde 0 (gestión e inventario).

        Devuelve también la primera respuesta, por los campos que no son de la página.
        """
        tamanio = min(TAMANIO_PAGINA, maximo)
        items: list[dict[str, Any]] = []
        primera: dict[str, Any] = {}
        total = 0
        pagina = 0
        while len(items) < maximo:
            datos = await self._obtener(
                ruta, {**filtros, "pagina": str(pagina), "tamanio": str(tamanio)}
            )
            primera = primera or datos
            items.extend(datos.get("items") or [])
            total = int(datos.get("total") or 0)
            if not datos.get("items") or len(items) >= total:
                break
            pagina += 1
        return items[:maximo], total, primera

    async def _cursor(
        self, ruta: str, filtros: Mapping[str, str], maximo: int
    ) -> tuple[list[dict[str, Any]], bool]:
        """Páginas `{items, siguienteCursor}` de servicio-operaciones (sin total)."""
        items: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            parametros = {**filtros, "limite": str(min(TAMANIO_PAGINA, maximo - len(items)))}
            if cursor:
                parametros["cursor"] = cursor
            datos = await self._obtener(ruta, parametros)
            items.extend(datos.get("items") or [])
            cursor = datos.get("siguienteCursor")
            if not cursor or len(items) >= maximo:
                break
        return items[:maximo], bool(cursor) or len(items) > maximo

    # --- servicio-gestion ---

    async def listar_parcelas(
        self,
        nombre: Annotated[str | None, Field(description="Parte del nombre de la parcela")] = None,
    ) -> dict[str, Any]:
        """Lista las parcelas (nombre, superficie en hectáreas, ubicación)."""
        items, total, _ = await self._paginas(
            f"{GESTION}/parcelas", _filtros(nombre=nombre), MAXIMO_POR_DEFECTO
        )
        return _listado([_campos(p, PARCELA) for p in items], total, total > len(items))

    async def listar_cultivos(self) -> dict[str, Any]:
        """Lista los cultivos registrados (nombre, variedad, unidad de producción)."""
        items, total, _ = await self._paginas(f"{GESTION}/cultivos", {}, MAXIMO_POR_DEFECTO)
        return _listado([_campos(c, CULTIVO) for c in items], total, total > len(items))

    async def listar_campanias(
        self,
        estado: Annotated[EstadoCampania | None, Field(description="Estado de la campaña")] = None,
        idParcela: Annotated[UUID | None, Field(description="ID de la parcela")] = None,
        idCultivo: Annotated[UUID | None, Field(description="ID del cultivo")] = None,
        maximo: Maximo = MAXIMO_POR_DEFECTO,
    ) -> dict[str, Any]:
        """Lista campañas, las más recientes primero (sin costos: ver obtener_campania)."""
        filtros = _filtros(estado=estado, idParcela=idParcela, idCultivo=idCultivo)
        items, total, _ = await self._paginas(f"{GESTION}/campanias", filtros, maximo)
        return _listado([_campos(c, CAMPANIA) for c in items], total, total > len(items))

    async def obtener_campania(self, idCampania: IdCampania) -> dict[str, Any]:
        """Datos de una campaña con su resumen: costo total, cantidad de costos y producción."""
        campania = await self._obtener(f"{GESTION}/campanias/{idCampania}")
        reducida = _campos(campania, CAMPANIA)
        reducida["resumen"] = campania.get("resumen")
        return reducida

    async def obtener_costos_campania(self, idCampania: IdCampania) -> dict[str, Any]:
        """Costos de una campaña con el costo total y el subtotal de cada categoría."""
        datos = await self._obtener(
            f"{GESTION}/campanias/{idCampania}/costos", {"tamanio": str(MAXIMO_POR_DEFECTO)}
        )
        items = [_campos(c, COSTO) for c in datos.get("items") or []]
        total = int(datos.get("total") or 0)
        return {
            "costoTotal": datos.get("costoTotal"),
            "subtotalesPorCategoria": datos.get("subtotalesPorCategoria"),
            **_listado(items, total, total > len(items)),
        }

    async def obtener_indicadores_campania(self, idCampania: IdCampania) -> dict[str, Any]:
        """Indicadores de una campaña: rendimiento y costo por hectárea, y por qué faltan."""
        datos: dict[str, Any] = await self._obtener(f"{GESTION}/campanias/{idCampania}/indicadores")
        return datos

    async def listar_historicos(
        self,
        idCultivo: Annotated[UUID | None, Field(description="ID del cultivo")] = None,
        idParcela: Annotated[UUID | None, Field(description="ID de la parcela")] = None,
        fechaFinalizacionDesde: Fecha = None,
        fechaFinalizacionHasta: Fecha = None,
        ordenarPor: Annotated[
            OrdenHistoricos,
            Field(description="Campo por el que se ordena, de mayor a menor"),
        ] = "fechaFinalizacion",
        maximo: Maximo = MAXIMO_POR_DEFECTO,
    ) -> dict[str, Any]:
        """Campañas finalizadas con costo total, costos por categoría, rendimiento y costo por
        hectárea. Sirve para comparar campañas o encontrar las de mayor costo o rendimiento."""
        filtros = _filtros(
            idCultivo=idCultivo,
            idParcela=idParcela,
            fechaFinalizacionDesde=fechaFinalizacionDesde,
            fechaFinalizacionHasta=fechaFinalizacionHasta,
            tamanio=TAMANIO_HISTORICOS,
        )
        datos = await self._obtener(f"{GESTION}/campanias/historicos", filtros)
        items = list(datos.get("items") or [])
        clave: Callable[[dict[str, Any]], Any]
        if ordenarPor == "fechaFinalizacion":
            clave = lambda h: h.get("fechaFinalizacion") or ""  # noqa: E731
        else:
            clave = lambda h: _decimal(h.get(ordenarPor)) or Decimal("-1")  # noqa: E731
        items.sort(key=clave, reverse=True)
        total = int(datos.get("total") or len(items))
        elegidos = [_campos(h, HISTORICO) for h in items[:maximo]]
        return _listado(elegidos, total, total > len(elegidos))

    # --- servicio-inventario ---

    async def consultar_estado_inventario(
        self,
        categoria: Annotated[CategoriaInsumo | None, Field(description="Categoría")] = None,
        soloStockBajo: Annotated[
            bool | None, Field(description="Solo los insumos con stock en o bajo el mínimo")
        ] = None,
        maximo: Maximo = MAXIMO_POR_DEFECTO,
    ) -> dict[str, Any]:
        """Stock actual, nivel mínimo y si está bajo de cada insumo, con un resumen."""
        filtros = _filtros(categoria=categoria, soloStockBajo=soloStockBajo)
        items, total, primera = await self._paginas(
            f"{INVENTARIO}/estado-inventario", filtros, maximo
        )
        elegidos = [_campos(i, ESTADO_INSUMO) for i in items]
        return {"resumen": primera.get("resumen"), **_listado(elegidos, total, total > len(items))}

    async def obtener_insumo(
        self, idInsumo: Annotated[UUID, Field(description="ID (UUID) del insumo")]
    ) -> dict[str, Any]:
        """Datos de un insumo: categoría, unidad, stock, nivel mínimo y costo unitario."""
        return _campos(await self._obtener(f"{INVENTARIO}/insumos/{idInsumo}"), INSUMO)

    # --- servicio-operaciones ---

    async def listar_labores(
        self,
        idCampania: Annotated[UUID | None, Field(description="ID de la campaña")] = None,
        estado: Annotated[EstadoLabor | None, Field(description="Estado de la labor")] = None,
        fechaDesde: Fecha = None,
        fechaHasta: Fecha = None,
        maximo: Maximo = MAXIMO_POR_DEFECTO,
    ) -> dict[str, Any]:
        """Labores de campo (siembra, fertilización, cosecha…) con los insumos consumidos.
        Exige idCampania o estado."""
        if idCampania is None and estado is None:
            raise ToolError("Indique idCampania o estado.")
        filtros = _filtros(
            idCampania=idCampania, estado=estado, fechaDesde=fechaDesde, fechaHasta=fechaHasta
        )
        items, truncado = await self._cursor(f"{OPERACIONES}/labores", filtros, maximo)
        return _listado([_labor(labor) for labor in items], len(items), truncado)

    async def listar_incidencias(
        self,
        idParcela: Annotated[UUID | None, Field(description="ID de la parcela")] = None,
        idCampania: Annotated[UUID | None, Field(description="ID de la campaña")] = None,
        tipo: Annotated[TipoIncidencia | None, Field(description="Tipo de incidencia")] = None,
        fechaDesde: Fecha = None,
        fechaHasta: Fecha = None,
        maximo: Maximo = MAXIMO_POR_DEFECTO,
    ) -> dict[str, Any]:
        """Incidencias observadas en campo (plagas, enfermedades, daños). Exige idParcela o
        idCampania."""
        if idParcela is None and idCampania is None:
            raise ToolError("Indique idParcela o idCampania.")
        filtros = _filtros(
            idParcela=idParcela,
            idCampania=idCampania,
            tipo=tipo,
            fechaDesde=fechaDesde,
            fechaHasta=fechaHasta,
        )
        items, truncado = await self._cursor(f"{OPERACIONES}/incidencias", filtros, maximo)
        return _listado([_incidencia(i) for i in items], len(items), truncado)


NOMBRES = (
    "listar_parcelas",
    "listar_cultivos",
    "listar_campanias",
    "obtener_campania",
    "obtener_costos_campania",
    "obtener_indicadores_campania",
    "listar_historicos",
    "consultar_estado_inventario",
    "obtener_insumo",
    "listar_labores",
    "listar_incidencias",
)
