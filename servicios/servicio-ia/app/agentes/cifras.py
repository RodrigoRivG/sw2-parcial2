"""Verificación de cifras de una respuesta redactada (spec-agentes.md 2.6, constitución §6).

Toda cifra del texto tiene que estar en los datos de las herramientas o en la pregunta. La
oración que tenga una cifra sin respaldo se quita: no se corrige (AC-03).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

SIN_CIFRAS_VERIFICABLES = (
    "No pude redactar una respuesta con cifras verificables. Revise los datos consultados."
)

# Número del texto: grupos de dígitos unidos por "." o "," o, si sigue un grupo de 3 dígitos,
# por un espacio ("38 250"). No empieza pegado a una letra: "COVID19" no es una cifra; sí puede
# terminar pegado a una unidad ("20kg").
_NUMERO_TEXTO = re.compile(r"(?<![^\W\d_])(?<![\d.,])\d+(?:(?:[.,]|[   ](?=\d{3}(?!\d)))\d+)*")
# En los datos los números vienen en formato de máquina: "38250.00", "20.000", "2026-11-02".
_NUMERO_DATO = re.compile(r"\d+(?:\.\d+)?")
_DIGITOS = re.compile(r"\d+")
_FIN_DE_ORACION = re.compile(r"(?<=[.!?…])\s+")
_CENTESIMOS = (Decimal(1), Decimal("0.1"), Decimal("0.01"))


@dataclass(frozen=True)
class Verificacion:
    texto: str
    omitidas: int


def _variantes(valor: Decimal) -> set[Decimal]:
    """El valor y sus redondeos a 0, 1 y 2 decimales ("38250.4567" respalda "38.250,46")."""
    valor = abs(valor)
    return {valor} | {valor.quantize(paso, rounding=ROUND_HALF_UP) for paso in _CENTESIMOS}


def _decimal(texto: str) -> Decimal | None:
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def lecturas(numero: str) -> set[Decimal]:
    """Todas las formas razonables de leer un número escrito en el texto.

    "20.000" es 20 (punto decimal, como envía el stock servicio-inventario) o veinte mil
    (punto de miles); "1,500" es 1,5 o mil quinientos. Basta que una lectura esté respaldada.
    """
    if re.search(r"[   ]", numero):  # "38 250,50": espacio de miles
        return lecturas(re.sub(r"[   ]", "", numero))

    separadores = re.findall(r"[.,]", numero)
    if not separadores:
        valor = _decimal(numero)
        return set() if valor is None else {valor}

    grupos = re.split(r"[.,]", numero)
    resultado: set[Decimal] = set()
    if len(set(separadores)) == 2:
        # Ambos: el último es el decimal y el otro, el de miles ("38.250,00" o "38,250.00").
        decimal = separadores[-1]
        miles = "," if decimal == "." else "."
        candidato = numero.replace(miles, "").replace(decimal, ".")
        if numero.count(decimal) == 1 and all(len(g) == 3 for g in grupos[1:-1]):
            valor = _decimal(candidato)
            if valor is not None:
                resultado.add(valor)
        return resultado

    separador = separadores[0]
    if len(separadores) == 1:
        valor = _decimal(numero.replace(separador, "."))
        if valor is not None:
            resultado.add(valor)
    if all(len(g) == 3 for g in grupos[1:]):
        valor = _decimal(numero.replace(separador, ""))
        if valor is not None:
            resultado.add(valor)
    return resultado


def _numeros_de_dato(texto: str) -> Iterable[Decimal]:
    for coincidencia in _NUMERO_DATO.finditer(texto):
        valor = _decimal(coincidencia.group())
        if valor is not None:
            yield valor
    # También cada grupo suelto de dígitos: partes de fechas ("2026-11-02" → 2026, 11, 2)
    # e IDs.
    for coincidencia in _DIGITOS.finditer(texto):
        yield Decimal(coincidencia.group())


def respaldadas(datos: Any, pregunta: str = "") -> set[Decimal]:
    """Cifras que el texto puede usar: las de los datos (con sus redondeos) y las de la pregunta.

    También la cantidad de elementos de cada lista: contar lo que se listó no es calcular.
    """
    cifras: set[Decimal] = set()

    def recorrer(valor: Any) -> None:
        if isinstance(valor, bool) or valor is None:
            return
        if isinstance(valor, int | float | Decimal):
            cifras.update(_variantes(Decimal(str(valor))))
        elif isinstance(valor, str):
            for numero in _numeros_de_dato(valor):
                cifras.update(_variantes(numero))
        elif isinstance(valor, dict):
            for clave, interno in valor.items():
                recorrer(clave)
                recorrer(interno)
        elif isinstance(valor, list | tuple):
            cifras.add(Decimal(len(valor)))
            for interno in valor:
                recorrer(interno)

    recorrer(datos)
    for coincidencia in _NUMERO_TEXTO.finditer(pregunta):
        for valor in lecturas(coincidencia.group()):
            cifras.update(_variantes(valor))
    return cifras


def cifras_sin_respaldo(oracion: str, permitidas: set[Decimal]) -> list[str]:
    sin_respaldo = []
    for coincidencia in _NUMERO_TEXTO.finditer(oracion):
        numero = coincidencia.group()
        opciones = lecturas(numero)
        if re.search(r"[   ]", numero):
            # "2 200" también puede ser dos números seguidos.
            partes = [lecturas(p) for p in re.split(r"[   ]", numero)]
            if all(p & permitidas for p in partes):
                continue
        if not opciones & permitidas:
            sin_respaldo.append(numero)
    return sin_respaldo


def oraciones(texto: str) -> list[list[str]]:
    """Por línea, sus oraciones (se conservan las listas y los saltos de línea)."""
    return [
        [o for o in _FIN_DE_ORACION.split(linea.strip()) if o]
        for linea in texto.strip().splitlines()
    ]


def verificar(texto: str, datos: Any, pregunta: str = "") -> Verificacion:
    permitidas = respaldadas(datos, pregunta)
    omitidas = 0
    lineas = []
    for linea in oraciones(texto):
        conservadas = []
        for oracion in linea:
            if cifras_sin_respaldo(oracion, permitidas):
                omitidas += 1
            else:
                conservadas.append(oracion)
        if conservadas or not linea:
            lineas.append(" ".join(conservadas))
    resultado = "\n".join(lineas).strip()
    resultado = re.sub(r"\n{3,}", "\n\n", resultado)
    if not resultado or (omitidas and not any(c.isalnum() for c in resultado)):
        return Verificacion(SIN_CIFRAS_VERIFICABLES, omitidas)
    return Verificacion(resultado, omitidas)
