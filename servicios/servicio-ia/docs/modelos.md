# Modelos de IA — `servicio-ia`

Documentación de cada modelo: propósito, datos, variables, entrenamiento, métricas de la versión vigente, limitaciones y cómo reentrenarlo (constitución §5). Se actualiza en el mismo commit que publica una versión.

Todos los resultados son **orientativos** (RN-13): no sustituyen una evaluación técnica agrícola.

---

## Conjunto de referencia (rendimiento y patrones)

El sistema empieza sin campañas finalizadas, así que los dos modelos tabulares se entrenan con un conjunto de referencia construido a partir de un dataset público, más las campañas finalizadas de `servicio-gestion` cuando existan (`--incluir-historicos`).

| | |
|---|---|
| Fuente | USDA Economic Research Service, *Commodity Costs and Returns*, sección "Recent Cost and Returns": `corn.csv`, `soybeans.csv` y `sorghum.csv` (<https://www.ers.usda.gov/data-products/commodity-costs-and-returns>) |
| Cita | U.S. Department of Agriculture, Economic Research Service. Commodity Costs and Returns data. |
| Licencia | Publicación del gobierno federal de EE. UU. (dominio público en EE. UU.) |
| Cobertura | Una fila por cultivo, región productiva y año: maíz 1996-2025 (180 filas), soya 1997-2025 (203), sorgo 1995-2025 (102). Total: 485 |
| Archivos | `datos/referencia/campanias_referencia.csv` (conjunto), `datos/referencia/fuentes.json` (URL, SHA-256 y conversiones), `datos/referencia/ipc_eeuu.csv` (deflactor) |
| Regenerar | `python -m app.ml.datos.preparar_ers` (descarga) o `--origen <carpeta>` (CSV ya descargados) |

### Transformaciones

1. Se excluye la región `U.S. total` (es un agregado de las demás).
2. Los ítems de costo del ERS se agrupan en las categorías de `CostoCampania` de `servicio-gestion`:

   | Categoría | Ítems del ERS |
   |---|---|
   | `INSUMO` | Seed, Fertilizer, Chemicals |
   | `MAQUINARIA` | Custom services; Fuel, lube, and electricity; Repairs; Capital recovery of machinery and equipment |
   | `MANO_DE_OBRA` | Hired labor |
   | `OTRO` | Purchased irrigation water; Interest on operating capital (o *inputs*, en sorgo); Taxes and insurance; General farm overhead |
   | Excluidos | Opportunity cost of land; Opportunity cost of unpaid labor (costos implícitos que un productor no registra) |

3. Los montos se deflactan a dólares de 2025 con el IPC de EE. UU. (BLS CPI-U, `CUUR0000SA0`, promedio anual).
4. Unidades: USD/acre × 2,47105 × 6,96 → **BOB/ha**; bushels/acre × kg por bushel (soya 27,2155; maíz y sorgo 25,4012) × 2,47105 → **kg/ha**.

### Limitaciones

- **Origen de los datos.** Son regiones productivas de EE. UU. Sus rendimientos son mayores que el promedio boliviano (soya: mediana de 2.825 kg/ha en la referencia frente a 2.360 kg/ha en Santa Cruz en 2025-2026, según ANAPO) y sus costos responden a otra estructura de precios. No se aplica un factor de calibración: la diferencia se reduce reentrenando con las campañas reales del sistema.
- **Variables disponibles.** Solo se usan variables que existen a la vez en el dataset y en `servicio-gestion`: el cultivo y el costo por hectárea de cada categoría. No hay clima, suelo ni variedad.
- **Cultivos.** Soya, maíz y sorgo. Otro cultivo responde `422 CULTIVO_NO_SOPORTADO`. El nombre del cultivo de gestión se compara sin tildes ni mayúsculas (`Soya`, `soja`, `Maíz`, `maiz duro`, `Sorgo granífero`…).

---

## `rendimiento` — Random Forest Regressor (RF-18, CU-14)

| | |
|---|---|
| Propósito | Estimar el rendimiento (kg/ha) de una campaña a partir de sus costos por hectárea |
| Variables | One-hot del cultivo (`SOYA`, `MAIZ`, `SORGO`) + costo por hectárea de `INSUMO`, `MANO_DE_OBRA`, `MAQUINARIA` y `OTRO` (BOB/ha) |
| Algoritmo | `RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=42)` |
| Validación | `KFold(5, shuffle=True, random_state=42)` con `cross_val_predict`; después se reentrena con todas las filas |
| Intervalo | Percentiles 10 y 90 de las estimaciones de los 300 árboles |
| Métrica principal | MAE (menor es mejor) |

**Versión vigente: 1** (conjunto de referencia, 485 filas ERS, semilla 42).

| Alcance | MAE (kg/ha) | RMSE (kg/ha) | R² |
|---|---|---|---|
| Global | 641,55 | 903,06 | 0,915 |
| Soya | 307,58 | 398,10 | 0,538 |
| Maíz | 1.014,95 | 1.293,75 | 0,522 |
| Sorgo | 647,29 | 780,08 | 0,399 |

Lectura honesta de las métricas: el R² global es alto porque gran parte de la varianza es la diferencia de rendimiento entre cultivos (el maíz rinde unas tres veces más que la soya). **Dentro de cada cultivo el modelo explica alrededor de la mitad de la variación** (R² de 0,40 a 0,54), con un error típico de unos 300 kg/ha en soya. Por eso cada estimación trae su intervalo y la marca de resultado orientativo.

Advertencias de la respuesta:

- `FUERA_DE_RANGO`: algún costo por hectárea es menor que la mitad del mínimo o mayor que el doble del máximo visto en el entrenamiento para ese cultivo. Se estima igual, con menos confianza.

---

## `patrones` — K-Means + Isolation Forest (RF-19, CU-15)

| | |
|---|---|
| Propósito | Agrupar campañas finalizadas por perfil de costo y rendimiento, y detectar las atípicas |
| Perfil | Costo total por hectárea / mediana del cultivo; rendimiento / mediana del cultivo; participación de cada categoría en el costo total. Así campañas de distintos cultivos son comparables |
| Algoritmos | `StandardScaler` → `KMeans(n_init=10, random_state=42)` con `k` de 3 a 6 elegido por silueta → `IsolationForest(contamination=0.05, random_state=42)` |
| Descripción de grupos | Desde el centroide: costo y rendimiento relativos "bajo" (< 0,85), "medio" o "alto" (> 1,15); si dos grupos coinciden, se agrega la categoría de costo con mayor participación |
| Motivos de anomalía | Variables del perfil con \|z\| > 2 respecto de la referencia, redactadas con plantillas fijas (sin modelo de lenguaje) |
| Métrica principal | Silueta (mayor es mejor) |

**Versión vigente: 1** (conjunto de referencia, 485 filas ERS, semilla 42).

| Métrica | Valor |
|---|---|
| `k` elegido | 5 |
| Silueta | 0,276 (k=3: 0,264; k=4: 0,264; k=5: 0,276; k=6: 0,275) |
| Proporción marcada como anómala en el entrenamiento | 5,2 % |

Grupos de la versión 1:

| Grupo | Descripción |
|---|---|
| 0 | Costo bajo · rendimiento bajo |
| 1 | Costo medio · rendimiento medio |
| 2 | Costo medio · rendimiento medio · más insumos |
| 3 | Costo medio · rendimiento medio · más maquinaria |
| 4 | Costo alto · rendimiento medio |

La silueta de 0,28 indica grupos con separación moderada: son perfiles orientativos, no categorías nítidas. Como los modelos se entrenan sobre la referencia, una campaña del sistema recibe grupo y marca de anomalía aunque sea la única finalizada.

---

## `clasificador` — MobileNetV3 Large con transfer learning (RF-20, RF-21, RF-22, CU-16)

| | |
|---|---|
| Propósito | Sugerir la enfermedad (o deficiencia) que muestra la foto de una hoja de soya o maíz. El técnico decide; la sugerencia se copia en la `clasificacion` de la incidencia de `servicio-operaciones` |
| Dónde corre | El mismo modelo en tres formatos: Keras en el servidor (`POST /clasificaciones` y videos), TFLite en Flutter y TF.js en Vue.js (sin conexión) |
| Arquitectura | `MobileNetV3Large` con pesos de ImageNet e `include_preprocessing=True`, sin la cabeza original → `GlobalAveragePooling2D` → `Dropout(0.2)` → `Dense(12, softmax)` |
| Entrenamiento | Fase 1: base congelada, Adam 1e-3, hasta 15 épocas. Fase 2: últimas 30 capas descongeladas (BatchNorm siempre en inferencia), Adam 1e-5, hasta 15 épocas. Lote 16, pesos por clase, `EarlyStopping(patience=3)` sobre la pérdida de validación. Semilla 42 y operaciones deterministas |
| Aumento de datos | Volteo horizontal y vertical, rotación ±10 %, zoom ±10 %, contraste y brillo ±10 %, recorte aleatorio de 256 a 224 |
| Métrica principal | F1 macro en la partición de prueba (mayor es mejor) |

### Datasets y licencias

| Dataset | Cultivo | Fotos usadas | Licencia |
|---|---|---|---|
| ASDID — Auburn Soybean Disease Image Dataset (Zenodo, registro 7304859; DOI `10.5061/dryad.41ns1rnj3`) | Soya: 8 clases | 400 (50 por clase), sobre todo de campo | CC0 1.0 |
| PlantVillage (Hughes y Salathé, 2015; Mendeley Data, versión sin aumento) | Maíz: 4 clases | 200 (50 por clase), de laboratorio | CC0 1.0 |

- Es una **muestra**: 50 fotos por clase, elegidas al azar con la semilla 42 y particionadas 70/15/15 por etiqueta (420 de entrenamiento, 84 de validación y 96 de prueba).
- Las fotos se piden sueltas dentro de los zips remotos con rangos de bytes. Se descargaron 1.777,5 MB en lugar de los 43 GB del dataset completo, y cada foto se reduce en memoria a 256 px por el lado menor.
- `datos/imagenes/manifiesto.csv` lista cada foto con su origen, partición y SHA-256. `datos/imagenes/fuentes.json` guarda las URL, los MD5 y el `.tar` del conjunto en `gs://<bucket>/datasets/imagenes/`.

### Etiquetas

Doce salidas en orden alfabético (el índice de la salida es la posición en esta lista y viaja en `etiquetas.json` y en los metadatos para dispositivos):

`MAIZ_MANCHA_GRIS`, `MAIZ_ROYA_COMUN`, `MAIZ_SANO`, `MAIZ_TIZON_NORTENO`, `SOYA_DEFICIENCIA_POTASIO`, `SOYA_MANCHA_DIANA`, `SOYA_MANCHA_OJO_RANA`, `SOYA_MILDIU`, `SOYA_ROYA`, `SOYA_SANA`, `SOYA_TIZON_BACTERIANO`, `SOYA_TIZON_CERCOSPORA`.

Si la probabilidad más alta es menor que el **umbral de la versión (0,50)**, la respuesta es `INDETERMINADO` con las tres más probables como alternativas. El umbral no es una salida del modelo: lo aplican el servidor y los dispositivos con el valor de los metadatos.

### Preprocesamiento (igual en servidor y dispositivos)

1. Corregir la orientación EXIF y convertir a RGB (sin transparencia).
2. Reducir a 256 px por el lado menor y recortar el centro a 224 × 224.
3. Pasar los valores **sin normalizar** (0–255, `float32`): el modelo incluye su propia normalización.

### Métricas de la versión vigente

**Versión vigente: 1** (600 fotos, semilla 42; 15 + 15 épocas; unos 8 minutos en CPU con 5 núcleos).

| Métrica (prueba, 96 fotos) | Valor |
|---|---|
| F1 macro | 0,893 |
| Exactitud | 0,896 |

| Etiqueta | Sensibilidad | Confusiones en prueba (8 fotos por clase) |
|---|---|---|
| `MAIZ_MANCHA_GRIS` | 0,875 | 1 como tizón norteño |
| `MAIZ_ROYA_COMUN` | 1,000 | — |
| `MAIZ_SANO` | 1,000 | — |
| `MAIZ_TIZON_NORTENO` | 0,875 | 1 como mancha gris |
| `SOYA_DEFICIENCIA_POTASIO` | 1,000 | — |
| `SOYA_MANCHA_DIANA` | 1,000 | — |
| `SOYA_MANCHA_OJO_RANA` | 0,625 | 3 como mancha diana |
| `SOYA_MILDIU` | 1,000 | — |
| `SOYA_ROYA` | 1,000 | — |
| `SOYA_SANA` | 0,625 | 2 como deficiencia de potasio, 1 como mancha diana |
| `SOYA_TIZON_BACTERIANO` | 1,000 | — |
| `SOYA_TIZON_CERCOSPORA` | 0,750 | 1 como mancha ojo de rana, 1 como tizón bacteriano |

Lectura honesta de las métricas:

- **La métrica es poco precisa.** Con 8 fotos por clase, una foto mal clasificada mueve la sensibilidad 0,125.
- **Lo que confunde el modelo tiene sentido:** las manchas foliares de la soya se parecen entre sí, y una hoja sana con algo de amarilleo se confunde con la deficiencia de potasio.
- **El maíz se ve mejor de lo que es:** PlantVillage es de laboratorio (hoja sola, fondo uniforme) y en el campo la precisión baja.
- **Para mejorar:** el camino es subir `--por-clase` y reentrenar.

### Archivos de la versión y uso en los dispositivos

| Archivo | Tamaño | Uso |
|---|---|---|
| `modelo.keras` | 12,1 MB | Servidor (no se entrega a los dispositivos) |
| `tflite/modelo.tflite` | 5,8 MB | Flutter (`tflite_flutter`), cuantizado a float16 |
| `tfjs/model.json` + `tfjs/group1-shard1of1.bin` | 3,1 MB | Vue.js (`tf.loadGraphModel`), *graph model* con pesos uint8 |

Antes de registrar la versión, el entrenamiento verifica tres cosas:

- las tres variantes tienen 12 salidas;
- Keras y TFLite eligen la misma categoría en las 96 fotos de prueba;
- el `model.json` declara 12 salidas.

Para usar el modelo en un dispositivo:

1. `GET /api/ia/v1/modelos/clasificador/dispositivo` devuelve `versionModelo` (`clasificador-<n>`), el umbral, la entrada, las etiquetas con su nombre y tipo de incidencia sugerido, y la ruta, el tamaño y el SHA-256 de cada archivo.
2. Cada archivo se descarga de `GET /api/ia/v1/modelos/clasificador/dispositivo/archivos/<ruta>`. Responde con `ETag` (el SHA-256), así que con `If-None-Match` contesta `304` si no cambió. En TF.js, cargar `model.json` desde esa URL: las rutas de los pesos son relativas.
3. Guardar en la incidencia `{"categoria", "confianza", "versionModelo", "origen": "DISPOSITIVO"}`. Volver a pedir los metadatos al recuperar la conexión para detectar una versión nueva.

### Rendimiento en el servidor (contenedor local, `mem_limit: 3g`)

| Prueba | Resultado |
|---|---|
| Foto JPEG de 4,2 MB (3000 × 3000) por el gateway | 0,58 s (objetivo: < 3 s, RNF-06) |
| Video MP4 de 60 s a 30 fps (30 fotogramas) | 2,5 s desde que se toma el trabajo (objetivo: < 60 s) |
| Carga del modelo (descarga, deserialización y calentamiento) | Unos 14 s; por eso la publicación responde sin esperarla |

### Limitaciones

- **Sorgo:** no hay un dataset público con licencia abierta, así que el modelo no lo cubre. Una foto de sorgo da otra categoría con baja confianza o `INDETERMINADO`.
- **Fotos que no son de hojas** (suelo, maquinaria, insectos): no hay una clase "otra cosa". El umbral lo mitiga, pero no lo resuelve.
- **Plagas:** las 12 etiquetas son enfermedades, una deficiencia y hojas sanas. Una plaga se registra manualmente.

---

## Cómo reentrenar y publicar

Dentro del contenedor del servicio (tiene las variables de entorno de Firestore, Cloud Storage, Keycloak y el gateway):

```bash
# 1. (Opcional) regenerar el conjunto de referencia desde el ERS
docker compose exec servicio-ia python -m app.ml.datos.preparar_ers

# 2. Entrenar; con --incluir-historicos suma las campañas finalizadas de servicio-gestion
docker compose exec servicio-ia python -m app.ml.entrenar rendimiento --incluir-historicos
docker compose exec servicio-ia python -m app.ml.entrenar patrones --incluir-historicos

# 3. Revisar las métricas impresas (o GET /api/ia/v1/modelos) y publicar como administrador
curl -X POST "$GATEWAY/api/ia/v1/modelos/rendimiento/versiones/<n>/publicacion" \
  -H "Authorization: Bearer $TOKEN_ADMIN" -H "Content-Type: application/json" \
  -d '{"justificacion": "..."}'   # obligatoria si la métrica principal es peor que la vigente
```

El clasificador se entrena fuera del contenedor del servicio. La conversión a TF.js necesita más que los 3 GB de `mem_limit` y el entrenamiento es una tarea offline. Se usa la imagen de desarrollo en la red de Compose, con las variables del servicio:

```bash
# 1. (Una vez) preparar la muestra de fotos en el volumen de caché y subir el .tar
./scripts/ejecutar.sh servicio-ia python -m app.ml.datos.preparar_imagenes --por-clase 50 --salida /cache/imagenes

# 2. Entrenar, exportar, verificar y registrar la CANDIDATA
docker compose exec -T servicio-ia env | grep -vE '^(HOSTNAME|HOME|PATH|TERM|PWD|SHLVL)=' > /tmp/ia.env
docker run --rm --network sw2_default --env-file /tmp/ia.env \
  -v sw2_ia-venv:/venv -v sw2_ia-cache:/cache -v "$PWD/servicios/servicio-ia:/app" -w /app \
  sw2/python-dev python -m app.ml.entrenar clasificador

# 3. Publicar igual que los otros modelos (POST .../modelos/clasificador/versiones/<n>/publicacion)
```

- Cada versión guarda en `gs://<bucket>/modelos/<nombre>/<idEntrenamiento>/` el modelo (`modelo.joblib`), el conjunto exacto usado (`dataset.csv`) y sus metadatos (`metadatos.json`), y en Firestore (`versiones_modelo`) el estado, las métricas y las estadísticas de referencia. El clasificador guarda `modelo.keras`, `tflite/`, `tfjs/`, `etiquetas.json` y `metadatos.json`, y referencia el `.tar` de fotos por su SHA-256.
- Con la misma semilla y el mismo conjunto de datos, el entrenamiento da las mismas métricas. Verificado en el clasificador: dos corridas dieron F1 macro 0,8934.
- Las instancias cargan la nueva versión vigente en menos de 60 s sin reiniciarse. La que atiende la publicación empieza a cargarla en segundo plano, sin demorar la respuesta: el clasificador tarda unos 14 s en cargar y el gateway corta a los 10 s.
- El emulador de Firestore no persiste: si se reinicia, hay que volver a registrar y publicar las versiones locales.
- Después de publicar, actualizar las tablas de métricas de este documento en el mismo commit.
