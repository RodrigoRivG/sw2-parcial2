"""Entrenamiento (spec-prediccion.md, Historia 3, escenarios 1 a 3)."""

import csv
import hashlib
import io
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from app.ml.entrenar import (
    a_bytes_joblib,
    armar_documento,
    dataset_csv,
    describir_grupos,
    entrenar_patrones,
    entrenar_rendimiento,
    historicos_a_filas,
    leer_referencia,
)
from app.modelos.cargador import deserializar_joblib
from app.modelos.esquemas import VersionModelo
from app.prediccion.variables import CategoriaCosto, Cultivo

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "referencia_pequena.csv"


def test_rendimiento_registra_metricas_por_cultivo_y_es_reproducible() -> None:
    filas = leer_referencia(FIXTURE)

    primero = entrenar_rendimiento(filas, semilla=7)
    segundo = entrenar_rendimiento(filas, semilla=7)

    assert primero.metricas == segundo.metricas
    assert {"mae", "rmse", "r2"} <= primero.metricas.keys()
    assert set(primero.metricas["porCultivo"]) == {"SOYA", "MAIZ", "SORGO"}
    assert primero.metrica_principal == {
        "nombre": "mae",
        "valor": primero.metricas["mae"],
        "sentido": "MENOR_ES_MEJOR",
    }
    assert len(primero.variables) == 7
    assert set(primero.referencia.cultivos) == {"SOYA", "MAIZ", "SORGO"}


def test_patrones_elige_k_por_silueta_y_describe_cada_grupo() -> None:
    entrenado = entrenar_patrones(leer_referencia(FIXTURE), semilla=7)

    k = entrenado.metricas["k"]
    assert 3 <= k <= 6
    assert entrenado.metricas["silueta"] == max(entrenado.metricas["siluetaPorK"].values())
    assert set(entrenado.artefacto) == {"escalador", "kmeans", "isolationForest", "descripciones"}
    descripciones = entrenado.artefacto["descripciones"]
    assert len(descripciones) == k
    assert len(set(descripciones.values())) == k  # sin descripciones repetidas
    assert entrenado.metrica_principal["sentido"] == "MAYOR_ES_MEJOR"


def test_descripcion_de_grupos() -> None:
    centroides = np.array(
        [
            [1.3, 0.8, 0.5, 0.1, 0.3, 0.1],
            [1.0, 1.0, 0.5, 0.1, 0.3, 0.1],
            [1.0, 1.0, 0.2, 0.1, 0.6, 0.1],
        ]
    )

    assert describir_grupos(centroides) == {
        "0": "Costo alto · rendimiento bajo",
        "1": "Costo medio · rendimiento medio",
        "2": "Costo medio · rendimiento medio · más maquinaria",
    }


def test_historicos_de_gestion_a_filas_por_hectarea() -> None:
    items = [
        {
            "nombreCultivo": "Soya",
            "superficieHectareas": "25.5000",
            "rendimientoPorHectarea": "3000.00",
            "costosPorCategoria": {
                "INSUMO": "20000.00",
                "MANO_DE_OBRA": "12000.00",
                "MAQUINARIA": "6250.00",
                "OTRO": "0.00",
            },
        },
        {"nombreCultivo": "Soya", "superficieHectareas": "10", "rendimientoPorHectarea": None},
        {"nombreCultivo": "Trigo", "superficieHectareas": "10", "rendimientoPorHectarea": "1"},
    ]

    (fila,) = historicos_a_filas(items)

    assert fila.origen == "SISTEMA"
    assert fila.cultivo is Cultivo.SOYA
    assert fila.rendimiento == 3000.0
    assert round(fila.costos[CategoriaCosto.INSUMO], 2) == round(20000 / 25.5, 2)
    assert fila.costos[CategoriaCosto.OTRO] == 0.0


def test_documento_y_artefactos_de_la_version() -> None:
    filas = leer_referencia(FIXTURE)
    entrenado = entrenar_rendimiento(filas, semilla=7)
    dataset = dataset_csv(filas)

    documento = armar_documento(
        "rendimiento",
        entrenado,
        filas,
        "modelos/rendimiento/abc",
        hashlib.sha256(dataset).hexdigest(),
        7,
        datetime(2026, 11, 5, tzinfo=UTC),
    )

    version = VersionModelo.desde_documento({**documento, "version": 1})
    assert version.dataset.filas_por_origen == {"ERS": 60}
    assert version.dataset.ruta == "modelos/rendimiento/abc/dataset.csv"
    assert version.estado.value == "CANDIDATA"
    assert version.semilla == 7
    filas_csv = list(csv.DictReader(io.StringIO(dataset.decode())))
    assert len(filas_csv) == 60
    modelo = deserializar_joblib(a_bytes_joblib(entrenado.artefacto))
    assert len(modelo.estimators_) == 300
