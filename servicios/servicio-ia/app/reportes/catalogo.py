"""Catálogo de fuentes de datos de los reportes: campos, tipos y etiquetas (spec-reportes.md 2.5).

Cada fuente se declara una vez; de aquí salen el esquema JSON del plan, la validación, el
catálogo de `GET /reportes/fuentes` y el mensaje de sistema del agente de reportes.
"""

from dataclasses import dataclass
from enum import StrEnum


class TipoCampo(StrEnum):
    TEXTO = "TEXTO"
    DECIMAL = "DECIMAL"
    ENTERO = "ENTERO"
    FECHA = "FECHA"
    FECHA_HORA = "FECHA_HORA"
    BOOLEANO = "BOOLEANO"
    ENUM = "ENUM"


@dataclass(frozen=True)
class Campo:
    nombre: str
    etiqueta: str
    tipo: TipoCampo
    por_defecto: bool = True
    valores: tuple[str, ...] = ()


@dataclass(frozen=True)
class Fuente:
    nombre: str
    descripcion: str
    campos: tuple[Campo, ...]
    orden_por_defecto: tuple[tuple[str, str], ...] = ()
    de_una_campania: bool = False

    def campo(self, nombre: str) -> Campo | None:
        return next((c for c in self.campos if c.nombre == nombre), None)

    @property
    def nombres(self) -> list[str]:
        return [c.nombre for c in self.campos]

    @property
    def columnas_por_defecto(self) -> list[str]:
        return [c.nombre for c in self.campos if c.por_defecto]


T, D, E, F, FH, B, EN = (
    TipoCampo.TEXTO,
    TipoCampo.DECIMAL,
    TipoCampo.ENTERO,
    TipoCampo.FECHA,
    TipoCampo.FECHA_HORA,
    TipoCampo.BOOLEANO,
    TipoCampo.ENUM,
)
ESTADOS_CAMPANIA = ("PLANIFICADA", "EN_CURSO", "FINALIZADA")
CATEGORIAS_COSTO = ("INSUMO", "MANO_DE_OBRA", "MAQUINARIA", "OTRO")
CATEGORIAS_INSUMO = ("SEMILLA", "FERTILIZANTE", "FITOSANITARIO")
UNIDADES = ("KILOGRAMO", "LITRO", "UNIDAD")
ESTADOS_LABOR = ("PROGRAMADA", "PENDIENTE", "CONFIRMADA", "RECHAZADA", "PENDIENTE_REVISION")
TIPOS_LABOR = (
    "PREPARACION_SUELO",
    "SIEMBRA",
    "FERTILIZACION",
    "RIEGO",
    "CONTROL_FITOSANITARIO",
    "DESHIERBE",
    "COSECHA",
    "OTRA",
)
TIPOS_INCIDENCIA = ("PLAGA", "ENFERMEDAD", "DANIO", "OTRO")

FUENTES: dict[str, Fuente] = {
    f.nombre: f
    for f in (
        Fuente(
            "PARCELAS",
            "Parcelas del predio con su superficie y ubicación",
            (
                Campo("nombre", "Parcela", T),
                Campo("superficieHectareas", "Superficie (ha)", D),
                Campo("ubicacion", "Ubicación", T),
                Campo("descripcion", "Descripción", T, por_defecto=False),
            ),
            (("nombre", "asc"),),
        ),
        Fuente(
            "CULTIVOS",
            "Cultivos registrados con su variedad",
            (
                Campo("nombre", "Cultivo", T),
                Campo("variedad", "Variedad", T),
                Campo("unidadMedida", "Unidad de producción", EN, False, ("KILOGRAMO",)),
                Campo("descripcion", "Descripción", T, por_defecto=False),
            ),
            (("nombre", "asc"),),
        ),
        Fuente(
            "CAMPANIAS",
            "Campañas agrícolas en cualquier estado (planificada, en curso o finalizada), "
            "sin costos ni rendimiento",
            (
                Campo("nombre", "Campaña", T),
                Campo("nombreParcela", "Parcela", T),
                Campo("nombreCultivo", "Cultivo", T),
                Campo("estado", "Estado", EN, valores=ESTADOS_CAMPANIA),
                Campo("fechaInicio", "Inicio", F),
                Campo("fechaFin", "Fin previsto", F),
                Campo("superficieHectareas", "Superficie (ha)", D),
                Campo("fechaFinalizacion", "Finalización", FH, por_defecto=False),
            ),
            (("fechaInicio", "desc"),),
        ),
        Fuente(
            "CAMPANIAS_FINALIZADAS",
            "Campañas finalizadas con producción, costos (total y por categoría), rendimiento "
            "por hectárea y costo por hectárea",
            (
                Campo("nombreCampania", "Campaña", T),
                Campo("nombreParcela", "Parcela", T),
                Campo("nombreCultivo", "Cultivo", T),
                Campo("variedad", "Variedad", T, por_defecto=False),
                Campo("superficieHectareas", "Superficie (ha)", D),
                Campo("fechaInicio", "Inicio", F, por_defecto=False),
                Campo("fechaFinalizacion", "Finalización", FH),
                Campo("duracionDias", "Duración (días)", E, por_defecto=False),
                Campo("produccion", "Producción (kg)", D),
                Campo("costoTotal", "Costo total (Bs)", D),
                Campo("costoInsumo", "Costo de insumos (Bs)", D, por_defecto=False),
                Campo("costoManoDeObra", "Costo de mano de obra (Bs)", D, por_defecto=False),
                Campo("costoMaquinaria", "Costo de maquinaria (Bs)", D, por_defecto=False),
                Campo("costoOtro", "Otros costos (Bs)", D, por_defecto=False),
                Campo("rendimientoPorHectarea", "Rendimiento (kg/ha)", D),
                Campo("costoPorHectarea", "Costo por ha (Bs/ha)", D),
            ),
            (("fechaFinalizacion", "desc"),),
        ),
        Fuente(
            "COSTOS_CAMPANIA",
            "Lista de costos registrados de una campaña",
            (
                Campo("fecha", "Fecha", F),
                Campo("categoria", "Categoría", EN, valores=CATEGORIAS_COSTO),
                Campo("descripcion", "Descripción", T),
                Campo("monto", "Monto (Bs)", D),
                Campo("origen", "Origen", EN, False, ("MANUAL", "SAGA")),
            ),
            (("fecha", "asc"),),
            de_una_campania=True,
        ),
        Fuente(
            "SUBTOTALES_CAMPANIA",
            "Subtotal de costos por categoría de una campaña",
            (
                Campo("categoria", "Categoría", EN, valores=CATEGORIAS_COSTO),
                Campo("subtotal", "Subtotal (Bs)", D),
            ),
            (("categoria", "asc"),),
            de_una_campania=True,
        ),
        Fuente(
            "INDICADORES_CAMPANIA",
            "Indicadores de una campaña: superficie, producción, costo total, rendimiento y "
            "costo por hectárea (una sola fila)",
            (
                Campo("nombre", "Campaña", T),
                Campo("estado", "Estado", EN, valores=ESTADOS_CAMPANIA),
                Campo("superficieHectareas", "Superficie (ha)", D),
                Campo("produccion", "Producción (kg)", D),
                Campo("costoTotal", "Costo total (Bs)", D),
                Campo("rendimientoPorHectarea", "Rendimiento (kg/ha)", D),
                Campo("costoPorHectarea", "Costo por ha (Bs/ha)", D),
                Campo("definitivo", "Definitivo", B),
            ),
            de_una_campania=True,
        ),
        Fuente(
            "INVENTARIO",
            "Insumos con su stock actual, nivel mínimo y si el stock está bajo",
            (
                Campo("nombre", "Insumo", T),
                Campo("categoria", "Categoría", EN, valores=CATEGORIAS_INSUMO),
                Campo("unidad", "Unidad", EN, valores=UNIDADES),
                Campo("stock", "Stock", D),
                Campo("nivelMinimo", "Nivel mínimo", D),
                Campo("stockBajo", "Stock bajo", B),
                Campo("fechaUltimaAlerta", "Última alerta", FH, por_defecto=False),
            ),
            (("nombre", "asc"),),
        ),
        Fuente(
            "LABORES",
            "Labores de campo (siembra, fertilización, cosecha…) con su responsable y los "
            "insumos consumidos",
            (
                Campo("tipoLabor", "Labor", EN, valores=TIPOS_LABOR),
                Campo("nombreCampania", "Campaña", T),
                Campo("nombreParcela", "Parcela", T),
                Campo("estado", "Estado", EN, valores=ESTADOS_LABOR),
                Campo("fechaProgramada", "Programada para", F, por_defecto=False),
                Campo("fechaEjecucion", "Ejecución", FH),
                Campo("responsable", "Responsable", T),
                Campo("insumos", "Insumos", T),
                Campo("observaciones", "Observaciones", T, por_defecto=False),
            ),
            (("fechaEjecucion", "desc"),),
        ),
        Fuente(
            "INCIDENCIAS",
            "Incidencias observadas en campo (plagas, enfermedades, daños) con su "
            "clasificación de IA",
            (
                Campo("tipo", "Tipo", EN, valores=TIPOS_INCIDENCIA),
                Campo("nombreParcela", "Parcela", T),
                Campo("nombreCampania", "Campaña", T, por_defecto=False),
                Campo("fechaObservacion", "Fecha", FH),
                Campo("descripcion", "Descripción", T),
                Campo("registradaPor", "Registrada por", T, por_defecto=False),
                Campo("clasificacion", "Clasificación de IA", T),
                Campo("confianzaClasificacion", "Confianza", D, por_defecto=False),
            ),
            (("fechaObservacion", "desc"),),
        ),
    )
}

# Título de la tabla cuando el plan no trae uno
TITULOS = {
    "PARCELAS": "Parcelas",
    "CULTIVOS": "Cultivos",
    "CAMPANIAS": "Campañas",
    "CAMPANIAS_FINALIZADAS": "Campañas finalizadas",
    "COSTOS_CAMPANIA": "Costos de la campaña",
    "SUBTOTALES_CAMPANIA": "Costos por categoría",
    "INDICADORES_CAMPANIA": "Indicadores de la campaña",
    "INVENTARIO": "Inventario de insumos",
    "LABORES": "Labores",
    "INCIDENCIAS": "Incidencias",
}
