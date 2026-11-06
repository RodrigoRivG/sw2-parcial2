"""Plan del reporte: esquema, validación y aplicación sobre los datos (spec-reportes.md 1.1 y 2.6).

`aplicar` filtra, ordena, limita y elige columnas. Nunca modifica un valor ni agrega columnas o
filas calculadas (RN-14, constitución v5.0.0 §6).
"""

import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints

from app.comun.errores import DetalleError
from app.comun.esquemas import ModeloEntrada
from app.reportes.catalogo import FUENTES, TITULOS, Campo, Fuente, TipoCampo

MAXIMO_TABLAS = 5
MAXIMO_FILAS = 500


class FormatoReporte(StrEnum):
    PDF = "PDF"
    XLSX = "XLSX"


class Operador(StrEnum):
    IGUAL = "igual"
    DISTINTO = "distinto"
    CONTIENE = "contiene"
    EMPIEZA_CON = "empiezaCon"
    MAYOR = "mayor"
    MAYOR_IGUAL = "mayorIgual"
    MENOR = "menor"
    MENOR_IGUAL = "menorIgual"
    ENTRE = "entre"
    EN = "en"
    VACIO = "vacio"
    NO_VACIO = "noVacio"


_COMUNES = {Operador.IGUAL, Operador.DISTINTO, Operador.EN, Operador.VACIO, Operador.NO_VACIO}
_ORDENABLES = _COMUNES | {
    Operador.MAYOR,
    Operador.MAYOR_IGUAL,
    Operador.MENOR,
    Operador.MENOR_IGUAL,
    Operador.ENTRE,
}
OPERADORES_POR_TIPO: dict[TipoCampo, set[Operador]] = {
    TipoCampo.TEXTO: _COMUNES | {Operador.CONTIENE, Operador.EMPIEZA_CON},
    TipoCampo.ENUM: _COMUNES,
    TipoCampo.BOOLEANO: {Operador.IGUAL, Operador.DISTINTO, Operador.VACIO, Operador.NO_VACIO},
    TipoCampo.DECIMAL: _ORDENABLES,
    TipoCampo.ENTERO: _ORDENABLES,
    TipoCampo.FECHA: _ORDENABLES,
    TipoCampo.FECHA_HORA: _ORDENABLES,
}
_EN_PALABRAS = {
    Operador.IGUAL: "es",
    Operador.DISTINTO: "no es",
    Operador.CONTIENE: "contiene",
    Operador.EMPIEZA_CON: "empieza con",
    Operador.MAYOR: "mayor que",
    Operador.MAYOR_IGUAL: "mayor o igual que",
    Operador.MENOR: "menor que",
    Operador.MENOR_IGUAL: "menor o igual que",
    Operador.ENTRE: "entre",
    Operador.EN: "es uno de",
    Operador.VACIO: "está vacío",
    Operador.NO_VACIO: "tiene valor",
}

Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class Filtro(ModeloEntrada):
    campo: str
    operador: Operador
    valor: Any = None


class Orden(ModeloEntrada):
    campo: str
    sentido: Literal["asc", "desc"] = "asc"


class TablaPlan(ModeloEntrada):
    fuente: str
    titulo: Texto | None = None
    columnas: list[str] = []
    filtros: list[Filtro] = []
    orden: list[Orden] = []
    limite: int | None = Field(default=None, ge=1, le=MAXIMO_FILAS)
    campania: Texto | None = None


class PlanReporte(ModeloEntrada):
    titulo: Texto | None = None
    formatos: list[FormatoReporte] = Field(default=[FormatoReporte.PDF], min_length=1)
    incluir_resumen: bool = True
    tablas: list[TablaPlan] = Field(min_length=1, max_length=MAXIMO_TABLAS)
    no_atendido: list[Annotated[str, StringConstraints(max_length=300)]] = []


# --- conversión de valores ----------------------------------------------------------------


def normalizar_texto(valor: Any) -> str:
    sin_tildes = unicodedata.normalize("NFKD", str(valor).strip().lower())
    return "".join(c for c in sin_tildes if not unicodedata.combining(c))


def _fecha(valor: Any) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    if "T" in texto:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).date()
    return date.fromisoformat(texto)


def _booleano(valor: Any) -> bool:
    if isinstance(valor, bool):
        return valor
    texto = normalizar_texto(valor)
    if texto in ("true", "si", "verdadero", "1"):
        return True
    if texto in ("false", "no", "falso", "0"):
        return False
    raise ValueError("debe ser verdadero o falso")


def _enum(valores: Sequence[str]) -> Callable[[Any], str]:
    def convertir(valor: Any) -> str:
        texto = str(valor).strip().upper().replace(" ", "_")
        if texto not in valores:
            raise ValueError(f"debe ser uno de: {', '.join(valores)}")
        return texto

    return convertir


def _decimal(valor: Any) -> Decimal:
    if isinstance(valor, bool):
        raise ValueError("debe ser un número")
    try:
        return Decimal(str(valor).strip())
    except InvalidOperation:
        raise ValueError("debe ser un número") from None


def _entero(valor: Any) -> int:
    numero = _decimal(valor)
    if numero != numero.to_integral_value():
        raise ValueError("debe ser un número entero")
    return int(numero)


def convertidor(campo: Campo) -> Callable[[Any], Any]:
    """Convierte un valor (del filtro o de la celda) al tipo del campo para compararlo."""
    if campo.tipo is TipoCampo.DECIMAL:
        return _decimal
    if campo.tipo is TipoCampo.ENTERO:
        return _entero
    if campo.tipo in (TipoCampo.FECHA, TipoCampo.FECHA_HORA):
        # Las fechas con hora se comparan por su día: "entre el 1 y el 31 de octubre" incluye
        # todo el 31.
        return _fecha
    if campo.tipo is TipoCampo.BOOLEANO:
        return _booleano
    if campo.tipo is TipoCampo.ENUM:
        return _enum(campo.valores)
    return normalizar_texto


def _vacio(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


# --- validación ---------------------------------------------------------------------------


def _validar_valor(filtro: Filtro, campo: Campo, ruta: str) -> list[DetalleError]:
    operador = filtro.operador
    if operador in (Operador.VACIO, Operador.NO_VACIO):
        return []
    convertir = convertidor(campo)
    if operador is Operador.ENTRE:
        if not isinstance(filtro.valor, list) or len(filtro.valor) != 2:
            return [DetalleError(campo=f"{ruta}.valor", mensaje="Debe ser una lista de 2 valores.")]
        valores = filtro.valor
    elif operador is Operador.EN:
        if not isinstance(filtro.valor, list) or not filtro.valor:
            return [DetalleError(campo=f"{ruta}.valor", mensaje="Debe ser una lista no vacía.")]
        valores = filtro.valor
    else:
        if _vacio(filtro.valor) or isinstance(filtro.valor, list | dict):
            return [DetalleError(campo=f"{ruta}.valor", mensaje="Debe tener un valor.")]
        valores = [filtro.valor]
    for valor in valores:
        try:
            convertir(valor)
        except ValueError as error:
            return [DetalleError(campo=f"{ruta}.valor", mensaje=f"«{valor}»: {error}.")]
    return []


def validar(plan: PlanReporte) -> list[DetalleError]:
    """Errores del plan con su ruta (`tablas[0].columnas[1]`) y los valores válidos."""
    errores: list[DetalleError] = []
    for i, tabla in enumerate(plan.tablas):
        ruta = f"tablas[{i}]"
        fuente = FUENTES.get(tabla.fuente)
        if fuente is None:
            errores.append(
                DetalleError(
                    campo=f"{ruta}.fuente",
                    mensaje=f"Fuente inexistente «{tabla.fuente}». Válidas: {', '.join(FUENTES)}.",
                )
            )
            continue
        validos = f"Campos de {fuente.nombre}: {', '.join(fuente.nombres)}."
        for j, columna in enumerate(tabla.columnas):
            if fuente.campo(columna) is None:
                errores.append(
                    DetalleError(
                        campo=f"{ruta}.columnas[{j}]",
                        mensaje=f"Campo «{columna}» no existe. {validos}",
                    )
                )
        if len(set(tabla.columnas)) != len(tabla.columnas):
            errores.append(DetalleError(campo=f"{ruta}.columnas", mensaje="Columnas repetidas."))
        for j, filtro in enumerate(tabla.filtros):
            ruta_filtro = f"{ruta}.filtros[{j}]"
            campo = fuente.campo(filtro.campo)
            if campo is None:
                errores.append(
                    DetalleError(
                        campo=f"{ruta_filtro}.campo",
                        mensaje=f"Campo «{filtro.campo}» no existe. {validos}",
                    )
                )
                continue
            permitidos = OPERADORES_POR_TIPO[campo.tipo]
            if filtro.operador not in permitidos:
                errores.append(
                    DetalleError(
                        campo=f"{ruta_filtro}.operador",
                        mensaje=f"«{filtro.operador}» no aplica a {campo.nombre} "
                        f"({campo.tipo.lower()}). Válidos: "
                        f"{', '.join(sorted(o.value for o in permitidos))}.",
                    )
                )
                continue
            errores.extend(_validar_valor(filtro, campo, ruta_filtro))
        for j, orden in enumerate(tabla.orden):
            if fuente.campo(orden.campo) is None:
                errores.append(
                    DetalleError(
                        campo=f"{ruta}.orden[{j}].campo",
                        mensaje=f"Campo «{orden.campo}» no existe. {validos}",
                    )
                )
        if fuente.de_una_campania and not tabla.campania:
            errores.append(
                DetalleError(
                    campo=f"{ruta}.campania",
                    mensaje=f"{fuente.nombre} es de una campaña: indique su nombre o ID.",
                )
            )
        if not fuente.de_una_campania and tabla.campania:
            errores.append(
                DetalleError(
                    campo=f"{ruta}.campania",
                    mensaje=f"{fuente.nombre} no es de una campaña: use un filtro.",
                )
            )
    return errores


# --- aplicación ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tabla:
    titulo: str
    fuente: str
    columnas: list[Campo]
    filas: list[list[Any]]
    total_origen: int

    @property
    def total_filas(self) -> int:
        return len(self.filas)


def _cumple(fila: Mapping[str, Any], filtro: Filtro, campo: Campo) -> bool:
    valor = fila.get(campo.nombre)
    if filtro.operador is Operador.VACIO:
        return _vacio(valor)
    if filtro.operador is Operador.NO_VACIO:
        return not _vacio(valor)
    if _vacio(valor):
        return filtro.operador is Operador.DISTINTO
    convertir = convertidor(campo)
    try:
        celda = convertir(valor)
    except ValueError:
        return False
    operador = filtro.operador
    if operador is Operador.EN:
        return any(celda == convertir(v) for v in filtro.valor)
    if operador is Operador.ENTRE:
        desde, hasta = (convertir(v) for v in filtro.valor)
        return bool(desde <= celda <= hasta)
    objetivo = convertir(filtro.valor)
    comparaciones: dict[Operador, Callable[[Any, Any], bool]] = {
        Operador.IGUAL: lambda a, b: a == b,
        Operador.DISTINTO: lambda a, b: a != b,
        Operador.CONTIENE: lambda a, b: b in a,
        Operador.EMPIEZA_CON: lambda a, b: a.startswith(b),
        Operador.MAYOR: lambda a, b: a > b,
        Operador.MAYOR_IGUAL: lambda a, b: a >= b,
        Operador.MENOR: lambda a, b: a < b,
        Operador.MENOR_IGUAL: lambda a, b: a <= b,
    }
    return comparaciones[operador](celda, objetivo)


def _ordenar(filas: list[Mapping[str, Any]], fuente: Fuente, orden: Sequence[Orden]) -> None:
    # Ordenamientos estables del último criterio al primero; los vacíos siempre al final.
    for criterio in reversed(orden):
        campo = fuente.campo(criterio.campo)
        if campo is None:
            continue
        convertir = convertidor(campo)

        def clave(
            fila: Mapping[str, Any],
            convertir: Callable[[Any], Any] = convertir,
            nombre: str = criterio.campo,
        ) -> Any:
            valor = fila.get(nombre)
            if _vacio(valor):
                return None
            try:
                return convertir(valor)
            except ValueError:
                return None

        con_valor = [f for f in filas if clave(f) is not None]
        sin_valor = [f for f in filas if clave(f) is None]
        con_valor.sort(key=clave, reverse=criterio.sentido == "desc")
        filas[:] = con_valor + sin_valor


def titulo_tabla(tabla: TablaPlan) -> str:
    return tabla.titulo or TITULOS[tabla.fuente]


def aplicar(tabla: TablaPlan, filas: Sequence[Mapping[str, Any]], total_origen: int) -> Tabla:
    """Filtra, ordena, limita y elige columnas. Las celdas son los valores tal cual."""
    fuente = FUENTES[tabla.fuente]
    filtros = [(f, c) for f in tabla.filtros if (c := fuente.campo(f.campo)) is not None]
    seleccion = [f for f in filas if all(_cumple(f, filtro, campo) for filtro, campo in filtros)]
    orden = tabla.orden or [
        Orden.model_validate({"campo": c, "sentido": s}) for c, s in fuente.orden_por_defecto
    ]
    _ordenar(seleccion, fuente, orden)
    if tabla.limite is not None:
        seleccion = seleccion[: tabla.limite]
    seleccion = seleccion[:MAXIMO_FILAS]
    nombres = tabla.columnas or fuente.columnas_por_defecto
    columnas = [c for n in nombres if (c := fuente.campo(n)) is not None]
    return Tabla(
        titulo=titulo_tabla(tabla),
        fuente=fuente.nombre,
        columnas=columnas,
        filas=[[f.get(c.nombre) for c in columnas] for f in seleccion],
        total_origen=total_origen,
    )


def _mostrar(valor: Any, campo: Campo | None) -> str:
    if campo is not None and campo.tipo is TipoCampo.BOOLEANO:
        try:
            return "Sí" if _booleano(valor) else "No"
        except ValueError:
            return str(valor)
    if campo is not None and campo.tipo is TipoCampo.ENUM:
        return str(valor).replace("_", " ").capitalize()
    return str(valor)


def describir_filtro(filtro: Filtro, fuente: Fuente) -> str:
    """El filtro en palabras para el PDF y el Excel: «Cultivo contiene "soya"»."""
    campo = fuente.campo(filtro.campo)
    etiqueta = campo.etiqueta if campo else filtro.campo
    palabras = _EN_PALABRAS[filtro.operador]
    if filtro.operador in (Operador.VACIO, Operador.NO_VACIO):
        return f"{etiqueta} {palabras}"
    if filtro.operador is Operador.ENTRE:
        desde, hasta = filtro.valor
        return f"{etiqueta} entre «{_mostrar(desde, campo)}» y «{_mostrar(hasta, campo)}»"
    if filtro.operador is Operador.EN:
        valores = ", ".join(f"«{_mostrar(v, campo)}»" for v in filtro.valor)
        return f"{etiqueta} {palabras}: {valores}"
    return f"{etiqueta} {palabras} «{_mostrar(filtro.valor, campo)}»"


def esquema_json(fuentes: Sequence[str] | None = None) -> dict[str, Any]:
    """Esquema del plan para el `format` de Ollama: fuentes y campos reales como enumeraciones.

    Con `fuentes`, solo esas fuentes y sus campos: el modelo no puede escribir un campo que no
    exista. Con varias, la pertenencia de cada campo a su tabla la verifica `validar`.
    """
    elegidas = [FUENTES[f] for f in fuentes or FUENTES if f in FUENTES]
    campos = sorted({c.nombre for f in elegidas for c in f.campos})
    valor: dict[str, Any] = {
        "anyOf": [
            {"type": "string"},
            {"type": "number"},
            {"type": "boolean"},
            {"type": "array", "items": {"type": ["string", "number"]}},
            {"type": "null"},
        ]
    }
    tabla = {
        "type": "object",
        "properties": {
            "fuente": {"type": "string", "enum": [f.nombre for f in elegidas]},
            "titulo": {"type": ["string", "null"]},
            "columnas": {"type": "array", "items": {"type": "string", "enum": campos}},
            "filtros": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "campo": {"type": "string", "enum": campos},
                        "operador": {"type": "string", "enum": [o.value for o in Operador]},
                        "valor": valor,
                    },
                    "required": ["campo", "operador", "valor"],
                },
            },
            "orden": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "campo": {"type": "string", "enum": campos},
                        "sentido": {"type": "string", "enum": ["asc", "desc"]},
                    },
                    "required": ["campo", "sentido"],
                },
            },
            "limite": {"type": ["integer", "null"]},
            "campania": {"type": ["string", "null"]},
        },
        "required": ["fuente", "columnas", "filtros", "orden", "limite", "campania"],
    }
    return {
        "type": "object",
        "properties": {
            "titulo": {"type": "string"},
            "formatos": {"type": "array", "items": {"type": "string", "enum": ["PDF", "XLSX"]}},
            "incluirResumen": {"type": "boolean"},
            "tablas": {"type": "array", "items": tabla},
            "noAtendido": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["titulo", "formatos", "incluirResumen", "tablas", "noAtendido"],
    }
