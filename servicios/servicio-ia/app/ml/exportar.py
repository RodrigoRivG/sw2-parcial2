"""Exportaciones del clasificador para los dispositivos (spec-vision.md 2.4, pasos 7 y 8).

Las tres variantes salen del mismo modelo entrenado: Keras (servidor), TFLite float16
(Flutter) y TF.js graph model uint8 (Vue.js).
"""

import json
import sys
import tempfile
import types
from pathlib import Path
from typing import Any

import numpy as np
import tensorflow as tf
from numpy.typing import NDArray


def exportar_keras(modelo: Any) -> bytes:
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "modelo.keras"
        modelo.save(ruta)
        return ruta.read_bytes()


def exportar_tflite(modelo: Any) -> bytes:
    convertidor = tf.lite.TFLiteConverter.from_keras_model(modelo)
    convertidor.optimizations = [tf.lite.Optimize.DEFAULT]
    convertidor.target_spec.supported_types = [tf.float16]
    contenido: bytes = convertidor.convert()
    return contenido


def exportar_tfjs(modelo: Any) -> dict[str, bytes]:
    """`model.json` y sus archivos de pesos (rutas relativas), cuantizados a uint8."""
    # El conversor importa tensorflow_decision_forests al cargarse, aunque solo lo usa para
    # modelos de ese tipo; el paquete fija otra versión de TensorFlow y no se instala.
    sys.modules.setdefault(
        "tensorflow_decision_forests", types.ModuleType("tensorflow_decision_forests")
    )
    from tensorflowjs.converters import tf_saved_model_conversion_v2 as conversor

    with tempfile.TemporaryDirectory() as carpeta:
        guardado = Path(carpeta) / "guardado"
        salida = Path(carpeta) / "tfjs"
        modelo.export(str(guardado), verbose=False)
        conversor.convert_tf_saved_model(
            str(guardado), str(salida), quantization_dtype_map={"uint8": "*"}
        )
        return {archivo.name: archivo.read_bytes() for archivo in sorted(salida.iterdir())}


def salidas_tflite(contenido: bytes, lote: NDArray[np.float32]) -> NDArray[np.float32]:
    """Probabilidades del modelo TFLite para cada imagen del lote."""
    interprete = tf.lite.Interpreter(model_content=contenido)
    interprete.allocate_tensors()
    entrada = interprete.get_input_details()[0]
    salida = interprete.get_output_details()[0]
    resultados = []
    for imagen in lote:
        interprete.set_tensor(entrada["index"], imagen[np.newaxis].astype(np.float32))
        interprete.invoke()
        resultados.append(interprete.get_tensor(salida["index"])[0])
    return np.asarray(resultados, dtype=np.float32)


def cantidad_salidas_tfjs(archivos: dict[str, bytes]) -> int:
    """Tamaño de la última dimensión de la salida declarada en `model.json`."""
    modelo = json.loads(archivos["model.json"])
    salidas = modelo["signature"]["outputs"]
    (salida,) = salidas.values()
    return int(salida["tensorShape"]["dim"][-1]["size"])


class ExportacionInvalida(Exception):
    pass


def verificar(
    modelo: Any,
    tflite: bytes,
    tfjs: dict[str, bytes],
    lote: NDArray[np.float32],
    cantidad_etiquetas: int,
) -> None:
    """Misma cantidad de salidas en las tres variantes y misma categoría en Keras y TFLite."""
    keras = np.asarray(modelo(lote, training=False))
    lite = salidas_tflite(tflite, lote)
    if keras.shape[-1] != cantidad_etiquetas or lite.shape[-1] != cantidad_etiquetas:
        raise ExportacionInvalida(f"Salidas: Keras {keras.shape[-1]}, TFLite {lite.shape[-1]}")
    if cantidad_salidas_tfjs(tfjs) != cantidad_etiquetas:
        raise ExportacionInvalida(f"Salidas TF.js: {cantidad_salidas_tfjs(tfjs)}")
    distintas = int((keras.argmax(axis=1) != lite.argmax(axis=1)).sum())
    if distintas:
        raise ExportacionInvalida(
            f"Keras y TFLite eligen distinta categoría en {distintas} imágenes"
        )
