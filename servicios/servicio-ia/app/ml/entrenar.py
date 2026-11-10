"""Entrenamiento de los modelos (spec-prediccion.md 2.5 y spec-vision.md 2.4).

Se ejecuta fuera del ciclo HTTP, dentro del contenedor del servicio:

    python -m app.ml.entrenar rendimiento [--incluir-historicos] [--semilla 42]
    python -m app.ml.entrenar patrones [--incluir-historicos] [--semilla 42]
    python -m app.ml.entrenar clasificador [--imagenes /cache/imagenes] [--semilla 42]

Registra la versión como CANDIDATA; se publica con POST /modelos/{nombre}/versiones/{v}/publicacion.
"""

import argparse
import asyncio
import csv
import hashlib
import io
import json
import sys
import uuid
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, silhouette_score
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.preprocessing import StandardScaler

from app.prediccion.variables import (
    CATEGORIAS,
    CULTIVOS,
    NOMBRES_PERFIL,
    CategoriaCosto,
    Cultivo,
    Referencia,
    calcular_referencia,
    normalizar_cultivo,
    perfil_patrones,
    vector_rendimiento,
)

RUTA_REFERENCIA = (
    Path(__file__).resolve().parents[2] / "datos" / "referencia" / "campanias_referencia.csv"
)
COLUMNAS_COSTO = {
    CategoriaCosto.INSUMO: "costoInsumoHa",
    CategoriaCosto.MANO_DE_OBRA: "costoManoDeObraHa",
    CategoriaCosto.MAQUINARIA: "costoMaquinariaHa",
    CategoriaCosto.OTRO: "costoOtroHa",
}
VARIABLES_RENDIMIENTO = [f"cultivo_{c.value}" for c in CULTIVOS] + [
    f"costo_{c.value}_ha" for c in CATEGORIAS
]
HIPERPARAMETROS_RENDIMIENTO = {"n_estimators": 300, "min_samples_leaf": 3}
RANGO_K = range(3, 7)
CONTAMINACION = 0.05
TAMANIO_PAGINA_HISTORICOS = 500


@dataclass(frozen=True)
class Fila:
    origen: str
    cultivo: Cultivo
    costos: Mapping[CategoriaCosto, float]
    rendimiento: float


@dataclass(frozen=True)
class Entrenado:
    artefacto: Any
    metricas: dict[str, Any]
    metrica_principal: dict[str, Any]
    referencia: Referencia
    variables: list[str]
    hiperparametros: dict[str, Any]
    adicionales: dict[str, Any]


# --- datos -------------------------------------------------------------------------------


def leer_referencia(ruta: Path = RUTA_REFERENCIA) -> list[Fila]:
    with ruta.open(encoding="utf-8") as archivo:
        return [
            Fila(
                origen=f["origen"],
                cultivo=Cultivo(f["cultivo"]),
                costos={c: float(f[columna]) for c, columna in COLUMNAS_COSTO.items()},
                rendimiento=float(f["rendimientoHa"]),
            )
            for f in csv.DictReader(archivo)
        ]


def _decimal(valor: Any) -> Decimal | None:
    if valor is None:
        return None
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return None


def historicos_a_filas(items: Iterable[Mapping[str, Any]]) -> list[Fila]:
    """Campañas finalizadas de servicio-gestion con indicadores y cultivo admitido → filas."""
    filas: list[Fila] = []
    for item in items:
        cultivo = normalizar_cultivo(str(item.get("nombreCultivo", "")))
        superficie = _decimal(item.get("superficieHectareas"))
        rendimiento = _decimal(item.get("rendimientoPorHectarea"))
        por_categoria = item.get("costosPorCategoria") or {}
        if cultivo is None or not superficie or superficie <= 0 or rendimiento is None:
            continue
        costos = {c: _decimal(por_categoria.get(c.value)) for c in CATEGORIAS}
        if any(v is None for v in costos.values()):
            continue
        filas.append(
            Fila(
                origen="SISTEMA",
                cultivo=cultivo,
                costos={c: float(v / superficie) for c, v in costos.items() if v is not None},
                rendimiento=float(rendimiento),
            )
        )
    return filas


async def leer_historicos() -> list[Fila]:
    """Todas las campañas finalizadas de servicio-gestion, a través del gateway."""
    from app.config import cargar_configuracion
    from app.integracion.gateway import ClienteGateway
    from app.integracion.token_servicio import TokenCuentaServicio

    config = cargar_configuracion()
    async with httpx.AsyncClient() as http:
        token = TokenCuentaServicio(
            http,
            config.keycloak_token_url,
            config.keycloak_client_id,
            config.keycloak_client_secret.get_secret_value(),
        )
        gateway = ClienteGateway(http, config.api_gateway_url, token, tiempo_limite=30)
        items: list[Mapping[str, Any]] = []
        pagina = 0
        while True:
            respuesta = await gateway.obtener(
                "/api/gestion/v1/campanias/historicos",
                {"pagina": str(pagina), "tamanio": str(TAMANIO_PAGINA_HISTORICOS)},
            )
            items += respuesta["items"]
            pagina += 1
            if pagina * TAMANIO_PAGINA_HISTORICOS >= int(respuesta["total"]):
                break
    return historicos_a_filas(items)


def dataset_csv(filas: Sequence[Fila]) -> bytes:
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\n")
    escritor.writerow(["origen", "cultivo", *COLUMNAS_COSTO.values(), "rendimientoHa"])
    for f in filas:
        escritor.writerow(
            [
                f.origen,
                f.cultivo.value,
                *(f"{f.costos[c]:.2f}" for c in CATEGORIAS),
                f"{f.rendimiento:.2f}",
            ]
        )
    return salida.getvalue().encode()


# --- modelos -----------------------------------------------------------------------------


def _metricas_regresion(reales: np.ndarray, estimados: np.ndarray) -> dict[str, float]:
    return {
        "mae": round(float(mean_absolute_error(reales, estimados)), 2),
        "rmse": round(float(np.sqrt(mean_squared_error(reales, estimados))), 2),
        "r2": round(float(r2_score(reales, estimados)), 4),
    }


def entrenar_rendimiento(filas: Sequence[Fila], semilla: int) -> Entrenado:
    x = np.array([vector_rendimiento(f.cultivo, f.costos) for f in filas])
    y = np.array([f.rendimiento for f in filas])
    modelo = RandomForestRegressor(random_state=semilla, n_jobs=-1, **HIPERPARAMETROS_RENDIMIENTO)
    estimados = cross_val_predict(modelo, x, y, cv=KFold(5, shuffle=True, random_state=semilla))
    metricas: dict[str, Any] = {
        "validacion": "KFold(5, shuffle, semilla)",
        **_metricas_regresion(y, estimados),
    }
    cultivos = np.array([f.cultivo.value for f in filas])
    metricas["porCultivo"] = {
        c.value: _metricas_regresion(y[cultivos == c.value], estimados[cultivos == c.value])
        for c in CULTIVOS
        if (cultivos == c.value).sum() >= 2
    }
    modelo.fit(x, y)
    return Entrenado(
        artefacto=modelo,
        metricas=metricas,
        metrica_principal={"nombre": "mae", "valor": metricas["mae"], "sentido": "MENOR_ES_MEJOR"},
        referencia=calcular_referencia((f.cultivo, f.costos, f.rendimiento) for f in filas),
        variables=VARIABLES_RENDIMIENTO,
        hiperparametros=HIPERPARAMETROS_RENDIMIENTO,
        adicionales={"unidad": "kg/ha"},
    )


_CATEGORIAS_CORTAS = ["insumos", "mano de obra", "maquinaria", "otros costos"]


def _nivel(valor: float) -> str:
    if valor < 0.85:
        return "bajo"
    if valor > 1.15:
        return "alto"
    return "medio"


def describir_grupos(centroides: np.ndarray) -> dict[str, str]:
    """Descripción de cada grupo desde su centroide (en la escala original del perfil)."""
    descripciones: dict[str, str] = {}
    usadas: Counter[str] = Counter()
    for grupo, centroide in enumerate(centroides):
        texto = f"Costo {_nivel(centroide[0])} · rendimiento {_nivel(centroide[1])}"
        usadas[texto] += 1
        if usadas[texto] > 1:
            texto += f" · más {_CATEGORIAS_CORTAS[int(np.argmax(centroide[2:]))]}"
        descripciones[str(grupo)] = texto
    return descripciones


def entrenar_patrones(filas: Sequence[Fila], semilla: int) -> Entrenado:
    referencia = calcular_referencia((f.cultivo, f.costos, f.rendimiento) for f in filas)
    perfiles = np.array(
        [perfil_patrones(f.cultivo, f.costos, f.rendimiento, referencia) for f in filas]
    )
    escalador = StandardScaler().fit(perfiles)
    escalados = escalador.transform(perfiles)

    siluetas: dict[str, float] = {}
    mejor: KMeans | None = None
    for k in RANGO_K:
        kmeans = KMeans(n_clusters=k, n_init=10, random_state=semilla).fit(escalados)
        siluetas[str(k)] = round(float(silhouette_score(escalados, kmeans.labels_)), 4)
        if mejor is None or siluetas[str(k)] > siluetas[str(mejor.n_clusters)]:
            mejor = kmeans
    assert mejor is not None
    bosque = IsolationForest(contamination=CONTAMINACION, random_state=semilla).fit(escalados)
    anomalas = float((bosque.predict(escalados) == -1).mean())
    descripciones = describir_grupos(escalador.inverse_transform(mejor.cluster_centers_))
    silueta = siluetas[str(mejor.n_clusters)]
    return Entrenado(
        artefacto={
            "escalador": escalador,
            "kmeans": mejor,
            "isolationForest": bosque,
            "descripciones": descripciones,
        },
        metricas={
            "silueta": silueta,
            "siluetaPorK": siluetas,
            "k": int(mejor.n_clusters),
            "proporcionAnomalas": round(anomalas, 4),
        },
        metrica_principal={"nombre": "silueta", "valor": silueta, "sentido": "MAYOR_ES_MEJOR"},
        referencia=referencia,
        variables=NOMBRES_PERFIL,
        hiperparametros={"k": list(RANGO_K), "nInit": 10, "contaminacion": CONTAMINACION},
        adicionales={"descripciones": descripciones},
    )


ENTRENADORES = {"rendimiento": entrenar_rendimiento, "patrones": entrenar_patrones}


# --- registro ----------------------------------------------------------------------------


def a_bytes_joblib(objeto: Any) -> bytes:
    salida = io.BytesIO()
    joblib.dump(objeto, salida)
    return salida.getvalue()


def armar_documento(
    nombre: str,
    entrenado: Entrenado,
    filas: Sequence[Fila],
    ruta: str,
    sha256_dataset: str,
    semilla: int,
    ahora: datetime,
) -> dict[str, Any]:
    return {
        "nombre": nombre,
        "estado": "CANDIDATA",
        "fechaEntrenamiento": ahora,
        "fechaPublicacion": None,
        "dataset": {
            "ruta": f"{ruta}/dataset.csv",
            "sha256": sha256_dataset,
            "filasPorOrigen": dict(Counter(f.origen for f in filas)),
        },
        "variables": entrenado.variables,
        "hiperparametros": entrenado.hiperparametros,
        "semilla": semilla,
        "metricas": entrenado.metricas,
        "metricaPrincipal": entrenado.metrica_principal,
        "rutaArtefactos": ruta,
        "referencia": entrenado.referencia.a_dict(),
        "adicionales": entrenado.adicionales,
        "justificacion": None,
    }


async def registrar(
    nombre: str, entrenado: Entrenado, filas: Sequence[Fila], semilla: int
) -> tuple[int, dict[str, Any] | None]:
    """Sube los artefactos y registra la CANDIDATA. Devuelve su versión y la vigente."""
    from app.config import cargar_configuracion
    from app.integracion.almacen_archivos import AlmacenS3
    from app.integracion.mongodb import crear_cliente_mongo
    from app.integracion.repositorio_versiones import RepositorioVersionesMongo

    config = cargar_configuracion()
    almacen = AlmacenS3(config.aws_bucket, config.s3_prefijo, config.aws_endpoint)
    repositorio = RepositorioVersionesMongo(
        crear_cliente_mongo(config.mongodb_uri.get_secret_value())[config.mongodb_base]
    )

    ruta = f"modelos/{nombre}/{uuid.uuid4()}"
    dataset = dataset_csv(filas)
    documento = armar_documento(
        nombre,
        entrenado,
        filas,
        ruta,
        hashlib.sha256(dataset).hexdigest(),
        semilla,
        datetime.now(UTC),
    )
    await almacen.subir(f"{ruta}/dataset.csv", dataset, "text/csv")
    await almacen.subir(
        f"{ruta}/modelo.joblib", a_bytes_joblib(entrenado.artefacto), "application/octet-stream"
    )
    metadatos = json.dumps(documento, ensure_ascii=False, default=str, indent=2).encode()
    await almacen.subir(f"{ruta}/metadatos.json", metadatos, "application/json")
    vigente = await repositorio.vigente(nombre)
    version = await repositorio.registrar_candidata(documento)
    return version, vigente


async def principal(opciones: argparse.Namespace) -> int:
    if opciones.modelo == "clasificador":
        # TensorFlow solo se importa para este modelo
        from app.ml import clasificador

        return await clasificador.principal(
            opciones.imagenes, clasificador.Configuracion(semilla=opciones.semilla)
        )
    filas = leer_referencia()
    if opciones.incluir_historicos:
        historicos = await leer_historicos()
        print(f"Campañas finalizadas de servicio-gestion agregadas: {len(historicos)}")
        filas += historicos
    entrenado = ENTRENADORES[opciones.modelo](filas, opciones.semilla)
    print(f"Filas por origen: {dict(Counter(f.origen for f in filas))}")
    print("Métricas:", json.dumps(entrenado.metricas, ensure_ascii=False, indent=2))
    version, vigente = await registrar(opciones.modelo, entrenado, filas, opciones.semilla)
    print(f"Registrada {opciones.modelo} versión {version} como CANDIDATA.")
    if vigente:
        print(f"Vigente: versión {vigente['version']}, {vigente['metricaPrincipal']}")
    else:
        print("No hay versión vigente.")
    return 0


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("modelo", choices=[*sorted(ENTRENADORES), "clasificador"])
    parser.add_argument("--incluir-historicos", action="store_true")
    parser.add_argument("--imagenes", type=Path, default=Path("/cache/imagenes"))
    parser.add_argument("--semilla", type=int, default=42)
    return asyncio.run(principal(parser.parse_args(argumentos)))


if __name__ == "__main__":
    sys.exit(main())
