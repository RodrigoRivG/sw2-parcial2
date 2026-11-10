"""Entrenamiento, evaluación, exportación y registro del clasificador (spec-vision.md 2.4).

python -m app.ml.entrenar clasificador [--imagenes /cache/imagenes] [--semilla 42]
"""

import csv
import gc
import hashlib
import io
import json
import tempfile
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import tensorflow as tf
from numpy.typing import NDArray
from PIL import Image
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score

from app.ml.exportar import exportar_keras, exportar_tfjs, exportar_tflite, verificar
from app.vision.etiquetas import CATEGORIAS, UMBRAL_POR_DEFECTO
from app.vision.imagenes import LADO_ENTRADA, LADO_REDUCCION

CARPETA_DATOS = Path(__file__).resolve().parents[2] / "datos" / "imagenes"
TAMANIO_LOTE = 16
ENTRADA = {
    "alto": LADO_ENTRADA,
    "ancho": LADO_ENTRADA,
    "canales": "RGB",
    "rango": "0-255",
    "recorte": "central tras reducir a 256 por el lado menor",
}


@dataclass(frozen=True)
class Particion:
    imagenes: NDArray[np.uint8]  # (N, 256, 256, 3)
    etiquetas: NDArray[np.int64]


@dataclass(frozen=True)
class Configuracion:
    arquitectura: str = "large"  # "small" solo para tests
    pesos: str | None = "imagenet"
    epocas_fase1: int = 15
    epocas_fase2: int = 15
    capas_descongeladas: int = 30
    semilla: int = 42


def _cuadrado(ruta: Path) -> NDArray[np.uint8]:
    """Lado menor a 256 y recorte central 256 × 256 (el recorte a 224 viene después)."""
    with Image.open(ruta) as original:
        imagen: Image.Image = original.convert("RGB")
        ancho, alto = imagen.size
        factor = LADO_REDUCCION / min(ancho, alto)
        imagen = imagen.resize(
            (max(LADO_REDUCCION, round(ancho * factor)), max(LADO_REDUCCION, round(alto * factor))),
            Image.Resampling.BILINEAR,
        )
        ancho, alto = imagen.size
        izquierda, arriba = (ancho - LADO_REDUCCION) // 2, (alto - LADO_REDUCCION) // 2
        recorte = imagen.crop(
            (izquierda, arriba, izquierda + LADO_REDUCCION, arriba + LADO_REDUCCION)
        )
        return np.asarray(recorte, dtype=np.uint8)


def leer_manifiesto(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def cargar_particiones(manifiesto: Sequence[dict[str, str]], carpeta: Path) -> dict[str, Particion]:
    indices = {c: i for i, c in enumerate(CATEGORIAS)}
    por_particion: dict[str, list[tuple[NDArray[np.uint8], int]]] = {}
    for fila in sorted(manifiesto, key=lambda f: f["archivo"]):
        por_particion.setdefault(fila["particion"], []).append(
            (_cuadrado(carpeta / fila["archivo"]), indices[fila["etiqueta"]])
        )
    return {
        nombre: Particion(
            np.stack([i for i, _ in filas]), np.asarray([e for _, e in filas], dtype=np.int64)
        )
        for nombre, filas in por_particion.items()
    }


def recorte_central(imagenes: NDArray[np.uint8]) -> NDArray[np.float32]:
    margen = (LADO_REDUCCION - LADO_ENTRADA) // 2
    return imagenes[:, margen : margen + LADO_ENTRADA, margen : margen + LADO_ENTRADA].astype(
        np.float32
    )


def construir_modelo(config: Configuracion) -> tuple[Any, Any]:
    clase = (
        tf.keras.applications.MobileNetV3Large
        if config.arquitectura == "large"
        else tf.keras.applications.MobileNetV3Small
    )
    base = clase(
        input_shape=(LADO_ENTRADA, LADO_ENTRADA, 3),
        include_top=False,
        weights=config.pesos,
        include_preprocessing=True,
        minimalistic=config.arquitectura != "large",
    )
    base.trainable = False
    entrada = tf.keras.Input((LADO_ENTRADA, LADO_ENTRADA, 3), name="imagen")
    x = base(entrada, training=False)  # BatchNorm siempre en modo inferencia
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    salida = tf.keras.layers.Dense(len(CATEGORIAS), activation="softmax", name="probabilidades")(x)
    return tf.keras.Model(entrada, salida, name="clasificador"), base


def _conjunto(particion: Particion, entrenamiento: bool, semilla: int) -> Any:
    datos = tf.data.Dataset.from_tensor_slices((particion.imagenes, particion.etiquetas))
    if entrenamiento:
        aumento = tf.keras.Sequential(
            [
                tf.keras.layers.RandomFlip("horizontal_and_vertical", seed=semilla),
                tf.keras.layers.RandomRotation(0.1, seed=semilla),
                tf.keras.layers.RandomZoom(0.1, seed=semilla),
                tf.keras.layers.RandomContrast(0.1, seed=semilla),
                tf.keras.layers.RandomBrightness(0.1, value_range=(0, 255), seed=semilla),
            ]
        )

        def preparar(imagen: Any, etiqueta: Any) -> Any:
            recorte = tf.image.random_crop(
                tf.cast(imagen, tf.float32), (LADO_ENTRADA, LADO_ENTRADA, 3), seed=semilla
            )
            return aumento(recorte, training=True), etiqueta

        datos = datos.shuffle(len(particion.etiquetas), seed=semilla).map(preparar)
    else:
        margen = (LADO_REDUCCION - LADO_ENTRADA) // 2
        datos = datos.map(
            lambda i, e: (
                tf.cast(
                    i[margen : margen + LADO_ENTRADA, margen : margen + LADO_ENTRADA], tf.float32
                ),
                e,
            )
        )
    return datos.batch(TAMANIO_LOTE).prefetch(tf.data.AUTOTUNE)


def _pesos_por_clase(etiquetas: NDArray[np.int64]) -> dict[int, float]:
    conteo = Counter(int(e) for e in etiquetas)
    total = len(etiquetas)
    return {c: total / (len(conteo) * n) for c, n in conteo.items()}


def _compilar(modelo: Any, tasa: float) -> None:
    # Con nombre: en Keras 3 el tercer posicional es `loss_weights`, no `metrics`.
    modelo.compile(
        optimizer=tf.keras.optimizers.Adam(tasa),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )


def entrenar(
    particiones: dict[str, Particion], config: Configuracion
) -> tuple[Any, dict[str, Any]]:
    tf.keras.utils.set_random_seed(config.semilla)
    tf.config.experimental.enable_op_determinism()
    modelo, base = construir_modelo(config)
    entrenamiento = _conjunto(particiones["entrenamiento"], True, config.semilla)
    validacion = _conjunto(particiones["validacion"], False, config.semilla)
    parada = tf.keras.callbacks.EarlyStopping(patience=3, restore_best_weights=True)
    pesos = _pesos_por_clase(particiones["entrenamiento"].etiquetas)
    historial: dict[str, Any] = {}

    _compilar(modelo, 1e-3)
    fase1 = modelo.fit(
        entrenamiento,
        validation_data=validacion,
        epochs=config.epocas_fase1,
        class_weight=pesos,
        callbacks=[parada],
        verbose=2,
    )
    historial["fase1Epocas"] = len(fase1.history["loss"])

    if config.epocas_fase2 > 0:
        base.trainable = True
        for capa in base.layers[: -config.capas_descongeladas]:
            capa.trainable = False
        _compilar(modelo, 1e-5)
        fase2 = modelo.fit(
            entrenamiento,
            validation_data=validacion,
            epochs=config.epocas_fase2,
            class_weight=pesos,
            callbacks=[parada],
            verbose=2,
        )
        historial["fase2Epocas"] = len(fase2.history["loss"])
    return modelo, historial


def evaluar(modelo: Any, prueba: Particion) -> dict[str, Any]:
    probabilidades = np.asarray(modelo.predict(recorte_central(prueba.imagenes), verbose=0))
    estimadas = probabilidades.argmax(axis=1)
    etiquetas = list(range(len(CATEGORIAS)))
    sensibilidad = recall_score(
        prueba.etiquetas, estimadas, labels=etiquetas, average=None, zero_division=0
    )
    return {
        "particion": "prueba",
        "imagenes": len(prueba.etiquetas),
        "exactitud": round(float(accuracy_score(prueba.etiquetas, estimadas)), 4),
        "f1Macro": round(
            float(
                f1_score(
                    prueba.etiquetas, estimadas, labels=etiquetas, average="macro", zero_division=0
                )
            ),
            4,
        ),
        "sensibilidadPorClase": {
            c: round(float(s), 4) for c, s in zip(CATEGORIAS, sensibilidad, strict=True)
        },
        "matrizConfusion": {
            "etiquetas": list(CATEGORIAS),
            "filas": confusion_matrix(prueba.etiquetas, estimadas, labels=etiquetas).tolist(),
        },
    }


def _archivo(ruta: str, datos: bytes) -> dict[str, Any]:
    return {"ruta": ruta, "tamanio": len(datos), "sha256": hashlib.sha256(datos).hexdigest()}


def recargar_sin_estado_de_entrenamiento(modelo: Any) -> Any:
    """Libera el grafo y el optimizador del entrenamiento antes de exportar.

    La conversión a TF.js de MobileNetV3 Large, sumada a lo que retiene `fit`, superaba
    los 3 GB del contenedor del servicio.
    """
    contenido = exportar_keras(modelo)
    del modelo
    tf.keras.backend.clear_session()
    gc.collect()
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "modelo.keras"
        ruta.write_bytes(contenido)
        return tf.keras.models.load_model(ruta, compile=False)


def artefactos(
    modelo: Any, lote_verificacion: NDArray[np.float32]
) -> tuple[dict[str, bytes], dict[str, list[dict[str, Any]]]]:
    """Las tres exportaciones verificadas y su descripción para los dispositivos."""
    tflite = exportar_tflite(modelo)
    tfjs = exportar_tfjs(modelo)
    verificar(modelo, tflite, tfjs, lote_verificacion, len(CATEGORIAS))
    archivos = {"modelo.keras": exportar_keras(modelo), "tflite/modelo.tflite": tflite}
    archivos.update({f"tfjs/{nombre}": datos for nombre, datos in tfjs.items()})
    exportaciones = {
        "tflite": [_archivo("tflite/modelo.tflite", tflite)],
        "tfjs": [_archivo(f"tfjs/{n}", d) for n, d in tfjs.items()],
    }
    return archivos, exportaciones


def armar_documento(
    metricas: dict[str, Any],
    historial: dict[str, Any],
    exportaciones: dict[str, Any],
    manifiesto: Sequence[dict[str, str]],
    conjunto: dict[str, str],
    ruta: str,
    config: Configuracion,
    ahora: datetime,
) -> dict[str, Any]:
    return {
        "nombre": "clasificador",
        "estado": "CANDIDATA",
        "fechaEntrenamiento": ahora,
        "fechaPublicacion": None,
        "dataset": {
            "ruta": conjunto["ruta"],
            "sha256": conjunto["sha256"],
            "filasPorOrigen": dict(Counter(f["fuente"] for f in manifiesto)),
        },
        "variables": ["imagen RGB 224x224, valores 0-255"],
        "hiperparametros": {
            "arquitectura": f"MobileNetV3{config.arquitectura.capitalize()}",
            "pesosIniciales": config.pesos,
            "epocasFase1": config.epocas_fase1,
            "epocasFase2": config.epocas_fase2,
            "capasDescongeladas": config.capas_descongeladas,
            "tamanioLote": TAMANIO_LOTE,
            **historial,
        },
        "semilla": config.semilla,
        "metricas": metricas,
        "metricaPrincipal": {
            "nombre": "f1Macro",
            "valor": metricas["f1Macro"],
            "sentido": "MAYOR_ES_MEJOR",
        },
        "rutaArtefactos": ruta,
        "referencia": None,
        "adicionales": {
            "etiquetas": list(CATEGORIAS),
            "umbral": UMBRAL_POR_DEFECTO,
            "entrada": ENTRADA,
            "exportaciones": exportaciones,
        },
        "justificacion": None,
    }


async def principal(carpeta: Path, config: Configuracion) -> int:
    from app.config import cargar_configuracion
    from app.integracion.almacen_archivos import AlmacenS3
    from app.integracion.mongodb import crear_cliente_mongo
    from app.integracion.repositorio_versiones import RepositorioVersionesMongo

    manifiesto = leer_manifiesto(CARPETA_DATOS / "manifiesto.csv")
    fuentes = json.loads((CARPETA_DATOS / "fuentes.json").read_text(encoding="utf-8"))
    if not fuentes.get("conjunto"):
        raise SystemExit("Falta subir el conjunto de imágenes (preparar_imagenes sin --sin-subir).")
    particiones = cargar_particiones(manifiesto, carpeta)
    print({nombre: len(p.etiquetas) for nombre, p in particiones.items()}, flush=True)

    modelo, historial = entrenar(particiones, config)
    metricas = evaluar(modelo, particiones["prueba"])
    print(
        json.dumps({k: v for k, v in metricas.items() if k != "matrizConfusion"}, indent=2),
        flush=True,
    )
    modelo = recargar_sin_estado_de_entrenamiento(modelo)
    archivos, exportaciones = artefactos(modelo, recorte_central(particiones["prueba"].imagenes))

    config_servicio = cargar_configuracion()
    almacen = AlmacenS3(
        config_servicio.aws_bucket, config_servicio.s3_prefijo, config_servicio.aws_endpoint
    )
    ruta = f"modelos/clasificador/{uuid.uuid4()}"
    conjunto = {"ruta": fuentes["conjunto"]["archivo"], "sha256": fuentes["conjunto"]["sha256"]}
    documento = armar_documento(
        metricas, historial, exportaciones, manifiesto, conjunto, ruta, config, datetime.now(UTC)
    )
    archivos["etiquetas.json"] = json.dumps(list(CATEGORIAS)).encode()
    archivos["metadatos.json"] = json.dumps(
        documento, default=str, ensure_ascii=False, indent=2
    ).encode()
    for nombre, datos in archivos.items():
        tipo = "application/json" if nombre.endswith(".json") else "application/octet-stream"
        await almacen.subir(f"{ruta}/{nombre}", datos, tipo)
        print(f"  {nombre}: {len(io.BytesIO(datos).getbuffer()) // 1024} KB", flush=True)
    repositorio = RepositorioVersionesMongo(
        crear_cliente_mongo(config_servicio.mongodb_uri.get_secret_value())[
            config_servicio.mongodb_base
        ]
    )
    vigente = await repositorio.vigente("clasificador")
    version = await repositorio.registrar_candidata(documento)
    print(f"Registrada clasificador versión {version} como CANDIDATA.")
    print(f"Vigente: {vigente['metricaPrincipal'] if vigente else 'ninguna'}")
    return 0
