"""Exportaciones del clasificador (spec-vision.md, Historia 2, escenario 5; constitución §8).

Entrena 1 época un modelo diminuto con la misma cabeza y las mismas exportaciones que el real.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from app.ml.clasificador import (
    Configuracion,
    artefactos,
    cargar_particiones,
    entrenar,
    evaluar,
    leer_manifiesto,
    recorte_central,
)
from app.ml.exportar import ExportacionInvalida, cantidad_salidas_tfjs, salidas_tflite, verificar
from app.vision.etiquetas import CATEGORIAS

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "imagenes"
CONFIG_DIMINUTA = Configuracion(
    arquitectura="small", pesos=None, epocas_fase1=1, epocas_fase2=0, semilla=3
)


@pytest.fixture(scope="module")
def entrenado() -> tuple[object, dict[str, object]]:
    particiones = cargar_particiones(leer_manifiesto(FIXTURES / "manifiesto.csv"), FIXTURES)
    modelo, _ = entrenar(particiones, CONFIG_DIMINUTA)
    return modelo, particiones


def test_las_tres_variantes_tienen_las_mismas_etiquetas_y_categorias(entrenado: tuple) -> None:
    modelo, particiones = entrenado
    lote = recorte_central(particiones["prueba"].imagenes)

    archivos, exportaciones = artefactos(modelo, lote)

    assert {"modelo.keras", "tflite/modelo.tflite", "tfjs/model.json"} <= archivos.keys()
    assert any(n.startswith("tfjs/") and n.endswith(".bin") for n in archivos)
    assert cantidad_salidas_tfjs({"model.json": archivos["tfjs/model.json"]}) == len(CATEGORIAS)
    lite = salidas_tflite(archivos["tflite/modelo.tflite"], lote)
    keras = np.asarray(modelo(lote, training=False))
    assert lite.shape == keras.shape == (len(lote), len(CATEGORIAS))
    assert (lite.argmax(axis=1) == keras.argmax(axis=1)).all()
    manifiesto_tfjs = json.loads(archivos["tfjs/model.json"])
    rutas_pesos = [p for grupo in manifiesto_tfjs["weightsManifest"] for p in grupo["paths"]]
    assert all("/" not in ruta for ruta in rutas_pesos)  # relativas: resuelven contra la descarga
    assert {a["ruta"] for a in exportaciones["tfjs"]} == {
        n for n in archivos if n.startswith("tfjs/")
    }
    assert all(
        len(a["sha256"]) == 64 and a["tamanio"] > 0 for f in exportaciones.values() for a in f
    )


def test_la_verificacion_detecta_salidas_que_no_coinciden(entrenado: tuple) -> None:
    modelo, particiones = entrenado
    lote = recorte_central(particiones["prueba"].imagenes)
    archivos, _ = artefactos(modelo, lote)
    tfjs = {"model.json": archivos["tfjs/model.json"]}

    with pytest.raises(ExportacionInvalida):
        verificar(modelo, archivos["tflite/modelo.tflite"], tfjs, lote, cantidad_etiquetas=13)


def test_metricas_de_prueba(entrenado: tuple) -> None:
    modelo, particiones = entrenado

    metricas = evaluar(modelo, particiones["prueba"])

    assert set(metricas) >= {"exactitud", "f1Macro", "sensibilidadPorClase", "matrizConfusion"}
    assert set(metricas["sensibilidadPorClase"]) == set(CATEGORIAS)
    assert len(metricas["matrizConfusion"]["filas"]) == len(CATEGORIAS)
    assert metricas["imagenes"] == len(particiones["prueba"].etiquetas)
