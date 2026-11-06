"""Manejador CLASIFICACION_VIDEO y agregación (spec-vision.md, Historia 3)."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from app.comun.errores import ErrorAplicacion
from app.modelos.cargador import ModeloCargado
from app.modelos.esquemas import VersionModelo
from app.trabajos.esquemas import Trabajo
from app.trabajos.estados import EstadoTrabajo
from app.vision.servicio import ServicioVision, agregar_video
from app.vision.video import InfoVideo
from tests.unit.vision.test_video import crear_video

CATEGORIAS = ["MAIZ_SANO", "SOYA_ROYA", "SOYA_SANA"]
AHORA = datetime(2026, 11, 5, tzinfo=UTC)


def _cargado(modelo: Any = None) -> ModeloCargado:
    version = VersionModelo.model_validate(
        {
            "nombre": "clasificador",
            "version": 4,
            "estado": "VIGENTE",
            "fechaEntrenamiento": AHORA,
            "dataset": {"ruta": "x", "sha256": "0", "filasPorOrigen": {}},
            "variables": [],
            "hiperparametros": {},
            "semilla": 1,
            "metricas": {},
            "metricaPrincipal": {"nombre": "f1Macro", "valor": 0.8, "sentido": "MAYOR_ES_MEJOR"},
            "rutaArtefactos": "modelos/clasificador/x",
            "adicionales": {
                "etiquetas": CATEGORIAS,
                "umbral": 0.5,
                "entrada": {},
                "exportaciones": {},
            },
        }
    )
    return ModeloCargado(version, modelo)


def test_predominante_por_probabilidad_promedio_entre_determinados() -> None:
    probabilidades = np.array(
        [
            [0.1, 0.8, 0.1],
            [0.2, 0.7, 0.1],
            [0.1, 0.3, 0.6],
            [0.4, 0.35, 0.25],
        ]  # el último: indeterminado
    )

    resultado = agregar_video([0.0, 1.0, 2.0, 3.0], probabilidades, InfoVideo(40, 10), _cargado())

    assert resultado.categoria_predominante == "SOYA_ROYA"
    assert resultado.confianza == Decimal("0.6000")  # promedio de 0.8, 0.7 y 0.3
    assert resultado.clasificacion.version_modelo == "clasificador-4"
    assert resultado.clasificacion.origen == "SERVIDOR"
    assert [(r.categoria, r.fotogramas_principal) for r in resultado.resumen] == [
        ("SOYA_ROYA", 2),
        ("INDETERMINADO", 1),
        ("SOYA_SANA", 1),
    ]
    assert [f.categoria for f in resultado.fotogramas] == [
        "SOYA_ROYA",
        "SOYA_ROYA",
        "SOYA_SANA",
        "INDETERMINADO",
    ]
    assert resultado.duracion_segundos == Decimal("4.00")


def test_todos_indeterminados() -> None:
    probabilidades = np.array([[0.4, 0.3, 0.3], [0.34, 0.33, 0.33]])

    resultado = agregar_video([0.0, 1.0], probabilidades, InfoVideo(20, 10), _cargado())

    assert resultado.categoria_predominante == "INDETERMINADO"
    assert resultado.nombre == "No se pudo identificar con suficiente confianza"


class AlmacenMemoria:
    def __init__(self) -> None:
        self.archivos: dict[str, bytes] = {}
        self.borrados: list[str] = []

    async def subir(self, ruta: str, datos: bytes, tipo: str) -> None:
        self.archivos[ruta] = datos

    async def descargar(self, ruta: str) -> bytes | None:
        return self.archivos.get(ruta)

    async def borrar(self, ruta: str) -> None:
        self.borrados.append(ruta)
        self.archivos.pop(ruta, None)


class CargadorFijo:
    def __init__(self, cargado: ModeloCargado | None) -> None:
        self.cargado = cargado

    def obtener(self, nombre: str) -> ModeloCargado:
        if self.cargado is None:
            raise ErrorAplicacion(503, "MODELO_NO_DISPONIBLE")
        return self.cargado


def _modelo_fijo(lote: np.ndarray, training: bool) -> np.ndarray:
    return np.tile(np.array([0.05, 0.9, 0.05], dtype=np.float32), (len(lote), 1))


def _trabajo(ruta: str) -> Trabajo:
    return Trabajo(
        id="t1",
        tipo="CLASIFICACION_VIDEO",
        estado=EstadoTrabajo.PROCESANDO,
        id_solicitante="tec",
        id_correlacion=None,
        parametros={"rutaVideo": ruta},
        fecha_creacion=AHORA,
    )


def _servicio(almacen: AlmacenMemoria, cargado: ModeloCargado | None) -> ServicioVision:
    return ServicioVision(CargadorFijo(cargado), None, almacen, None)  # type: ignore[arg-type]


async def test_procesa_y_borra_el_video(tmp_path: Path) -> None:
    almacen = AlmacenMemoria()
    almacen.archivos["temporales/videos/v.mp4"] = crear_video(tmp_path / "v.mp4", 4).read_bytes()

    resultado = await _servicio(almacen, _cargado(_modelo_fijo)).procesar_video(
        _trabajo("temporales/videos/v.mp4")
    )

    assert resultado["categoriaPredominante"] == "SOYA_ROYA"
    assert resultado["confianza"] == "0.9000"
    assert len(resultado["fotogramas"]) == 4
    assert resultado["orientativo"] is True
    assert almacen.borrados == ["temporales/videos/v.mp4"]


async def test_sin_modelo_falla_y_borra_igual(tmp_path: Path) -> None:
    almacen = AlmacenMemoria()
    almacen.archivos["temporales/videos/v.mp4"] = crear_video(tmp_path / "v.mp4", 2).read_bytes()

    with pytest.raises(ErrorAplicacion) as error:
        await _servicio(almacen, None).procesar_video(_trabajo("temporales/videos/v.mp4"))

    assert error.value.codigo == "MODELO_NO_DISPONIBLE"
    assert almacen.borrados == ["temporales/videos/v.mp4"]


async def test_video_borrado_a_mano_es_video_no_disponible() -> None:
    almacen = AlmacenMemoria()

    with pytest.raises(ErrorAplicacion) as error:
        await _servicio(almacen, _cargado(_modelo_fijo)).procesar_video(
            _trabajo("temporales/videos/no.mp4")
        )

    assert error.value.codigo == "VIDEO_NO_DISPONIBLE"
