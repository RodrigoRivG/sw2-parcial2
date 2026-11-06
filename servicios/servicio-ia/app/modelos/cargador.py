"""Carga en memoria de la versión vigente de cada modelo (spec-prediccion.md 2.6, constitución §3).

Se carga al arrancar y se revisa cada `MODELOS_INTERVALO_REVISION_SEGUNDOS`; nunca en cada
solicitud. Los artefactos vienen del bucket propio del servicio (constitución §4).
"""

import asyncio
import contextlib
import io
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import joblib

from app.comun.errores import ErrorAplicacion
from app.integracion.almacen_archivos import AlmacenArchivos
from app.integracion.repositorio_versiones import RepositorioVersionesFirestore
from app.modelos.esquemas import VersionModelo

Deserializador = Callable[[bytes], Any]
_logger = logging.getLogger("app.modelos.cargador")


def deserializar_joblib(datos: bytes) -> Any:
    return joblib.load(io.BytesIO(datos))


class EstadoCarga(StrEnum):
    CARGADO = "CARGADO"
    SIN_PUBLICAR = "SIN_PUBLICAR"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ModeloCargado:
    version: VersionModelo
    modelo: Any


@dataclass(frozen=True)
class _Registro:
    deserializar: Deserializador
    archivo: str


class CargadorModelos:
    def __init__(
        self,
        repositorio: RepositorioVersionesFirestore,
        almacen: AlmacenArchivos,
        intervalo: float = 60.0,
    ) -> None:
        self._repositorio = repositorio
        self._almacen = almacen
        self._intervalo = intervalo
        self._registros: dict[str, _Registro] = {}
        self._cargados: dict[str, ModeloCargado] = {}
        self._estados: dict[str, EstadoCarga] = {}
        self._tarea: asyncio.Task[None] | None = None
        self._candados: dict[str, asyncio.Lock] = {}
        self._pendientes: set[asyncio.Task[None]] = set()

    def registrar(
        self,
        nombre: str,
        deserializar: Deserializador = deserializar_joblib,
        archivo: str = "modelo.joblib",
    ) -> None:
        self._registros[nombre] = _Registro(deserializar, archivo)
        self._estados[nombre] = EstadoCarga.SIN_PUBLICAR
        self._candados[nombre] = asyncio.Lock()

    def revisar_en_segundo_plano(self, nombre: str) -> None:
        """Tras publicar: carga ya, sin esperar el ciclo ni demorar la respuesta.

        Cargar el clasificador (descarga, deserialización y calentamiento) supera el tiempo
        límite del gateway.
        """
        if nombre not in self._registros:
            return
        tarea = asyncio.create_task(self._revisar(nombre), name=f"cargar-{nombre}")
        self._pendientes.add(tarea)
        tarea.add_done_callback(self._pendientes.discard)

    async def esperar_pendientes(self) -> None:
        await asyncio.gather(*self._pendientes)

    def obtener(self, nombre: str) -> ModeloCargado:
        cargado = self._cargados.get(nombre)
        if cargado is None:
            raise ErrorAplicacion(503, "MODELO_NO_DISPONIBLE")
        return cargado

    def estado(self, nombre: str) -> EstadoCarga:
        return self._estados[nombre]

    async def comprobar(self, nombre: str) -> None:
        """Comprobación de salud informativa: falla si el modelo no está cargado."""
        if self._estados.get(nombre) is not EstadoCarga.CARGADO:
            raise RuntimeError(f"{nombre}: {self._estados.get(nombre)}")

    async def revisar(self) -> None:
        for nombre in self._registros:
            await self._revisar(nombre)

    async def _revisar(self, nombre: str) -> None:
        async with self._candados[nombre]:  # el ciclo y una publicación no cargan dos veces
            await self._revisar_sin_candado(nombre)

    async def _revisar_sin_candado(self, nombre: str) -> None:
        try:
            documento = await self._repositorio.vigente(nombre)
            if documento is None:
                if nombre not in self._cargados:
                    self._estados[nombre] = EstadoCarga.SIN_PUBLICAR
                return
            version = VersionModelo.desde_documento(documento)
            actual = self._cargados.get(nombre)
            if actual is not None and actual.version.version == version.version:
                return
            registro = self._registros[nombre]
            datos = await self._almacen.descargar(f"{version.ruta_artefactos}/{registro.archivo}")
            if datos is None:
                raise FileNotFoundError(f"{version.ruta_artefactos}/{registro.archivo}")
            modelo = await asyncio.to_thread(registro.deserializar, datos)
        except Exception as error:
            self._estados[nombre] = (
                EstadoCarga.CARGADO if nombre in self._cargados else EstadoCarga.ERROR
            )
            _logger.error(
                "No se pudo cargar la versión vigente del modelo",
                extra={"modelo": nombre, "motivo": repr(error)},
            )
            return
        self._cargados[nombre] = ModeloCargado(version, modelo)  # reemplazo atómico
        self._estados[nombre] = EstadoCarga.CARGADO
        _logger.info("Modelo cargado", extra={"modelo": nombre, "version": version.version})

    def iniciar(self) -> None:
        self._tarea = asyncio.create_task(self._ciclo(), name="cargador-modelos")

    async def _ciclo(self) -> None:
        while True:
            await self.revisar()
            await asyncio.sleep(self._intervalo)

    async def detener(self) -> None:
        tareas = [t for t in (self._tarea, *self._pendientes) if t is not None and not t.done()]
        for tarea in tareas:
            tarea.cancel()
        for tarea in tareas:
            with contextlib.suppress(asyncio.CancelledError):
                await tarea
