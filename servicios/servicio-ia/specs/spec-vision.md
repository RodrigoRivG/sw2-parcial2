# Clasificación de imágenes y video — `servicio-ia`

| Campo | Valor |
|---|---|
| Servicio | `servicio-ia` |
| Archivo | `specs/spec-vision.md` |
| Estado | Spec en borrador · Plan y tareas en borrador |
| Fecha | 2026-11-04 |
| Constitución | v3.1.0 (secciones 1, 4, 5, 7, 8 y 9) |
| Trazabilidad | CU-16 · RF-20, RF-21, RF-22 · RN-13 · RNF-06 · proceso 6 y Módulo 5 del documento de requisitos |
| Depende de | `spec-base.md`, `spec-trabajos.md` (tipo `CLASIFICACION_VIDEO`) y `spec-prediccion.md` (módulo `modelos`, `AlmacenArchivos`). Contrato de `servicio-operaciones` para guardar la clasificación de una incidencia (`servicio-operaciones/specs/spec-incidencias.md`, Historia 2) |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## 1.1 Contexto

El técnico de campo fotografía un cultivo y quiere saber si muestra una enfermedad (CU-16). Hay tres caminos con **el mismo modelo** (constitución §5):

| Camino | Dónde corre | Spec |
|---|---|---|
| Sin conexión | Flutter (TensorFlow Lite) y Vue.js (TensorFlow.js), con el modelo descargado antes | Este servicio solo **entrega** los modelos exportados (RF-21) |
| Con conexión | `POST /clasificaciones` en este servicio, con el modelo completo de TensorFlow (RF-20) | Esta spec |
| Video | `POST /clasificaciones/videos`: se extraen fotogramas y se clasifican, como trabajo asíncrono (RF-22) | Esta spec |

El resultado no se guarda en la incidencia desde aquí. El cliente lo copia en la `clasificacion` de la incidencia que registra en `servicio-operaciones` (constitución §1). Por eso la respuesta trae un objeto `clasificacion` con exactamente el formato que ese servicio acepta.

### Datasets públicos elegidos

| Dataset | Cultivo | Clases usadas | Licencia |
|---|---|---|---|
| **ASDID** — Auburn Soybean Disease Image Dataset (Dryad y Zenodo, DOI `10.5061/dryad.41ns1rnj3`) | Soya | Sana, tizón bacteriano, tizón por Cercospora, mildiu, mancha ojo de rana, roya, mancha diana, deficiencia de potasio (unas 10.000 fotos de campo y de fondo controlado, de unos 5,9 MB cada una, en un zip por clase) | CC0 1.0 |
| **PlantVillage** (Hughes y Salathé, 2015; Mendeley Data), solo las clases de maíz | Maíz | Sana, roya común, mancha gris (Cercospora), tizón foliar del norte (unas 3.800 fotos de laboratorio de 256 × 256) | CC0 1.0 |

**Muestra, no el dataset completo.** ASDID pesa 43 GB por la resolución de sus fotos. Para no esperar horas de descarga, se usa una **muestra de 50 fotos por clase** en las 12 clases (600 fotos, unos 2,4 GB de descarga de ASDID y unos pocos MB de PlantVillage). Las fotos se piden sueltas dentro de cada zip de Zenodo con pedidos de rangos de bytes (verificado: Zenodo responde `206`), sin bajar el zip entero. Es un proyecto académico: con transfer learning sobre MobileNetV3, 50 por clase alcanzan para demostrar el flujo. La cantidad es un parámetro (`--por-clase`); si la exactitud no alcanza, se sube y se reentrena (AC-05).

**Por qué estos:** la soya es el cultivo principal de la región, y ASDID trae la roya, la enfermedad que más preocupa en Santa Cruz, fotografiada en campo. PlantVillage es el dataset de referencia para maíz. Ambos son CC0, así que se pueden redistribuir sin restricciones.

**Limitaciones conocidas (RN-13), documentadas en `docs/modelos.md`:**

- **Sorgo:** no hay un dataset público con licencia abierta. El clasificador no lo cubre; una foto de sorgo dará una categoría de otro cultivo con baja confianza o `INDETERMINADO`.
- **Maíz:** las fotos de PlantVillage son de laboratorio (hoja sola, fondo uniforme). En fotos de campo la precisión baja.
- **Fotos que no son de hojas** (suelo, maquinaria, insectos): el modelo no tiene una clase para eso. El umbral de confianza (`INDETERMINADO`) lo mitiga, no lo resuelve.

Alternativas descartadas: SoyNet (India; CC BY 4.0, pero repite clases de ASDID con menos fotos de campo) y el dataset de soya de IEEE DataPort (requiere suscripción).

### Etiquetas

| Etiqueta | Nombre para mostrar | Cultivo | Tipo de incidencia sugerido |
|---|---|---|---|
| `SOYA_SANA` | Soya sana | Soya | — |
| `SOYA_ROYA` | Roya asiática de la soya | Soya | `ENFERMEDAD` |
| `SOYA_MANCHA_OJO_RANA` | Mancha ojo de rana | Soya | `ENFERMEDAD` |
| `SOYA_TIZON_BACTERIANO` | Tizón bacteriano | Soya | `ENFERMEDAD` |
| `SOYA_TIZON_CERCOSPORA` | Tizón por Cercospora | Soya | `ENFERMEDAD` |
| `SOYA_MILDIU` | Mildiu | Soya | `ENFERMEDAD` |
| `SOYA_MANCHA_DIANA` | Mancha diana | Soya | `ENFERMEDAD` |
| `SOYA_DEFICIENCIA_POTASIO` | Deficiencia de potasio | Soya | `OTRO` |
| `MAIZ_SANO` | Maíz sano | Maíz | — |
| `MAIZ_ROYA_COMUN` | Roya común del maíz | Maíz | `ENFERMEDAD` |
| `MAIZ_MANCHA_GRIS` | Mancha gris de la hoja | Maíz | `ENFERMEDAD` |
| `MAIZ_TIZON_NORTENO` | Tizón foliar del norte | Maíz | `ENFERMEDAD` |

Además, `INDETERMINADO` ("No se pudo identificar con suficiente confianza") cuando la probabilidad más alta es menor que el umbral de la versión (0,50 por defecto). No es una salida del modelo; la aplican el servidor y los dispositivos con el mismo umbral, que viaja en los metadatos.

Los tipos sugeridos usan los valores de `TipoIncidencia` de `servicio-operaciones` (`PLAGA`, `ENFERMEDAD`, `DANIO`, `OTRO`). Son una ayuda para completar el formulario; el técnico decide.

## 1.2 Escenarios de usuario y pruebas

### Historia 1 — Clasificar una foto con el servidor (Prioridad: P1)

Como técnico de campo con conexión, quiero enviar la foto de una hoja y recibir la categoría con su confianza, para registrarla en la incidencia (RF-20).

**Por qué esta prioridad:** es el requisito de Deep Learning en el servidor y lo que demuestra el modelo completo.

**Prueba independiente:** con un modelo pequeño entrenado sobre las imágenes de `tests/fixtures` y publicado en los emuladores.

**Escenarios de aceptación:**

1. **Dado** una foto JPEG o PNG de hasta 10 MB, **cuando** el técnico la envía a `POST /clasificaciones`, **entonces** recibe `201` con:
   - `categoria`, su nombre para mostrar, `confianza` (texto decimal de 0 a 1 con 4 decimales), el cultivo y el tipo de incidencia sugerido;
   - las 3 categorías más probables;
   - la versión del modelo, `orientativo: true` y el aviso de RN-13;
   - `clasificacion` `{ categoria, confianza, versionModelo, origen: "SERVIDOR" }`, lista para enviarla a `servicio-operaciones` sin cambios.
2. **Dado** una foto donde la probabilidad más alta es menor que el umbral, **entonces** `categoria = INDETERMINADO`, con las 3 más probables igual.
3. **Dado** una foto tomada en vertical con orientación EXIF, **entonces** se corrige antes de clasificar.
4. **Dado** un archivo que no es JPEG ni PNG (aunque tenga esa extensión), una imagen dañada o una imagen menor de 64 × 64 píxeles, **entonces** `400 IMAGEN_INVALIDA`.
5. **Dado** un archivo de más de 10 MB, **entonces** `400 ARCHIVO_DEMASIADO_GRANDE`, sin leerlo entero.
6. **Dado** el servidor sin una versión vigente del clasificador, **entonces** `503 MODELO_NO_DISPONIBLE`.
7. **Dado** una clasificación hecha, **entonces** se guarda el resultado (sin la imagen) y la imagen no queda en ningún almacenamiento (constitución §4).
8. **Dado** un usuario sin `tecnico_campo`, **entonces** `403 SIN_PERMISO`.

---

### Historia 2 — Descargar el modelo para usarlo sin conexión (Prioridad: P1)

Como aplicación Flutter o Vue.js, quiero saber cuál es la versión vigente del clasificador y descargarla con su suma de verificación, para clasificar en el campo sin conexión con el mismo modelo que el servidor (RF-21, constitución §5).

**Prueba independiente:** con una versión publicada en los emuladores que incluye sus exportaciones.

**Escenarios de aceptación:**

1. **Dado** una versión vigente, **cuando** la aplicación pide `GET /modelos/clasificador/dispositivo`, **entonces** recibe:
   - la versión (`clasificador-<n>`), las etiquetas en orden de salida del modelo con sus nombres, cultivos y tipos sugeridos, y el umbral;
   - la forma de la entrada (224 × 224, RGB, valores de 0 a 255; el modelo hace su propia normalización);
   - para `tflite` y `tfjs`, la lista de archivos con su ruta de descarga, tamaño y SHA-256.
2. **Dado** la ruta de un archivo, **cuando** se pide `GET /modelos/clasificador/dispositivo/archivos/{ruta}`, **entonces** se recibe el archivo con su `Content-Type`, `ETag` (su SHA-256) y `Cache-Control: private, max-age=86400`.
3. **Dado** una solicitud con `If-None-Match` igual al `ETag`, **entonces** `304` sin cuerpo (la aplicación no lo vuelve a bajar).
4. **Dado** el modelo TF.js, **entonces** `model.json` referencia sus archivos de pesos con rutas relativas que resuelven contra la misma ruta de descarga, así `tf.loadGraphModel` los encuentra enviando el mismo token.
5. **Dado** una versión exportada, **entonces** las tres variantes (Keras del servidor, TFLite y TF.js) tienen la misma versión, la misma lista de etiquetas y la misma cantidad de salidas, y para las imágenes de `tests/fixtures` Keras y TFLite eligen la misma categoría (constitución §8).
6. **Dado** una ruta que no pertenece a la versión vigente, **entonces** `404 ARCHIVO_MODELO_NO_ENCONTRADO`.

---

### Historia 3 — Clasificar un video (Prioridad: P2)

Como técnico de campo, quiero enviar un video corto recorriendo el cultivo y saber qué se ve con más frecuencia, sin tomar foto por foto (RF-22).

**Prueba independiente:** con un video de 5 s en `tests/fixtures`, generado a partir de las imágenes de prueba.

**Escenarios de aceptación:**

1. **Dado** un video MP4, MOV o WebM de hasta 50 MB y 60 s, **cuando** se envía a `POST /clasificaciones/videos`, **entonces** se recibe `202` con el trabajo (`spec-trabajos.md`).
2. **Dado** el trabajo procesado, **entonces** su `resultado` trae:
   - la categoría predominante (mayor probabilidad promedio entre los fotogramas) con su confianza y la `clasificacion` lista para `servicio-operaciones`;
   - un resumen por categoría (fotogramas en que fue la principal y confianza promedio);
   - la lista de fotogramas analizados con su segundo, categoría y confianza.
3. **Dado** un video de 60 s, **entonces** se analizan como máximo 30 fotogramas repartidos de forma uniforme (uno por segundo si dura 30 s o menos).
4. **Dado** un archivo que no se puede decodificar como video, o que dura más de 60 s, **entonces** `400 VIDEO_INVALIDO` al recibirlo, sin crear el trabajo. Más de 50 MB → `400 ARCHIVO_DEMASIADO_GRANDE`.
5. **Dado** el trabajo terminado (bien o mal), **entonces** el video se borra del almacenamiento temporal.
6. **Dado** un video cuyos fotogramas son todos `INDETERMINADO`, **entonces** la predominante es `INDETERMINADO`.

---

### Historia 4 — Entrenar, exportar y publicar el clasificador (Prioridad: P1)

Como administrador de TI, quiero entrenar el clasificador con los datasets públicos, exportarlo para los dispositivos y publicarlo con el mismo procedimiento que los otros modelos (`spec-prediccion.md`, Historia 3).

**Escenarios de aceptación:**

1. **Dado** las imágenes preparadas, **cuando** se ejecuta `python -m app.ml.entrenar clasificador`, **entonces** se crea una versión `CANDIDATA` con el modelo Keras, sus exportaciones TFLite y TF.js, las etiquetas, el umbral y las métricas sobre el conjunto de prueba: exactitud, F1 macro, sensibilidad por clase y matriz de confusión.
2. **Dado** la publicación, **entonces** la métrica principal es el F1 macro (mayor es mejor) y se aplica la regla de `spec-prediccion.md` (`METRICAS_INFERIORES` salvo justificación).
3. **Dado** la versión publicada, **entonces** el servidor la carga sin reiniciar y `GET /modelos/clasificador/dispositivo` informa la nueva versión.

---

### Historia 5 — Preparar las imágenes de forma reproducible (Prioridad: P2)

Como desarrollador, quiero obtener la muestra de imágenes desde los datasets públicos con un comando, sin descargar los 43 GB de ASDID ni llenar el disco, y saber de dónde sale cada imagen.

**Escenarios de aceptación:**

1. **Dado** las URL de los zips de ASDID en Zenodo y la fuente de PlantVillage, **cuando** se ejecuta `python -m app.ml.datos.preparar_imagenes --por-clase 50`, **entonces**:
   - de cada zip de ASDID se lee solo su índice y se descargan, con pedidos de rangos de bytes, 50 fotos elegidas al azar con semilla fija; de PlantVillage, 50 por clase de maíz;
   - cada foto se reduce a 256 px por el lado menor (JPEG de calidad 90) apenas llega, y el original no se guarda en disco;
   - se escribe `datos/imagenes/manifiesto.csv` (archivo de origen dentro del zip, etiqueta, fuente, partición, SHA-256 de la foto reducida), con partición entrenamiento, validación y prueba (70/15/15) estratificada por etiqueta y con semilla fija;
   - se escribe `datos/imagenes/fuentes.json`, con DOI, URL, MD5 publicado de cada zip, licencia y fecha.
2. **Dado** una ejecución que se corta, **cuando** se vuelve a ejecutar, **entonces** retoma: las fotos ya reducidas no se vuelven a descargar.
3. **Dado** la misma semilla y `--por-clase`, **entonces** se eligen las mismas fotos.
4. **Dado** el conjunto preparado, **entonces** se sube una sola vez a Cloud Storage como `datasets/imagenes/<sha256>.tar`, y cada versión del clasificador guarda la referencia a ese archivo (constitución §5: el conjunto usado queda junto a la versión).
5. **Dado** el manifiesto, **entonces** está en el repositorio; las imágenes no.

### Casos borde

- **Imagen enorme en píxeles** (por ejemplo, 20.000 × 20.000 en un PNG de pocos MB): se rechaza con `400 IMAGEN_INVALIDA` antes de decodificarla por completo (límite de 40 megapíxeles).
- **PNG con transparencia o en escala de grises:** se convierte a RGB.
- **Varias clasificaciones a la vez:** la inferencia corre en un hilo con un modelo ya cargado; TensorFlow admite llamadas concurrentes a `predict` sobre el mismo modelo.
- **Se publica una versión nueva mientras un dispositivo descarga la anterior:** los archivos de cada versión viven en su propia carpeta y no se borran al retirarla, así la descarga en curso termina bien; el dispositivo verá la nueva versión en su próxima consulta.
- **Clases balanceadas:** con 50 fotos por clase no hace falta compensar el desbalance; los pesos por clase de 2.4 quedan en 1 y solo actúan si se cambia `--por-clase` de forma distinta por fuente.
- **Video con rotación en sus metadatos:** OpenCV la aplica al leer los fotogramas (comportamiento por defecto en las versiones recientes).
- **El trabajo de video no encuentra el archivo temporal** (se borró a mano): `FALLIDO` con `VIDEO_NO_DISPONIBLE`.

## 1.3 Requisitos

### Requisitos funcionales

- **RQ-VIS-01:** `POST /clasificaciones` clasifica una imagen JPEG o PNG con la versión vigente de `clasificador` y responde con el formato de la Historia 1.
- **RQ-VIS-02:** validar la imagen por su contenido (no por la extensión ni el `Content-Type` declarado), con los límites de 10 MB, 64 × 64 px como mínimo y 40 megapíxeles como máximo.
- **RQ-VIS-03:** aplicar el umbral de la versión para `INDETERMINADO`.
- **RQ-VIS-04:** guardar cada resultado en `clasificaciones` (sin la imagen) con la versión del modelo, y borrarlo a los 90 días (TTL).
- **RQ-VIS-05:** `GET /modelos/clasificador/dispositivo` y `GET /modelos/clasificador/dispositivo/archivos/{ruta}` entregan la versión vigente para los dispositivos, con SHA-256, `ETag` y respuesta `304`.
- **RQ-VIS-06:** `POST /clasificaciones/videos` valida el video, lo guarda de forma temporal y crea un trabajo `CLASIFICACION_VIDEO` con un tiempo límite de 3 minutos.
- **RQ-VIS-07:** el manejador del trabajo extrae hasta 30 fotogramas uniformes, los clasifica, arma el resultado de la Historia 3 y borra el video.
- **RQ-VIS-08:** el entrenamiento produce en una sola versión el modelo Keras, el TFLite y el TF.js, con las mismas etiquetas, y registra las métricas de la Historia 4.
- **RQ-VIS-09:** el conjunto de imágenes se prepara con un comando reproducible y su manifiesto se versiona en el repositorio.

### Entidades clave

| Entidad | Colección | Campos principales |
|---|---|---|
| `ClasificacionImagen` | `clasificaciones` | `id`, `idSolicitante`, `fecha`, `versionModelo`, `categoria`, `confianza`, `alternativas`, `sha256Imagen`, `fechaExpiracion` |
| `VersionModelo` (de `spec-prediccion.md`) con `nombre = clasificador` | `versiones_modelo` | Además: `etiquetas`, `umbral`, `entrada`, `exportaciones` (`tflite` y `tfjs` con sus archivos, tamaños y SHA-256), `datasetImagenes` (ruta y SHA-256 del `.tar`) |

`sha256Imagen` permite saber si la misma foto se clasificó dos veces, sin guardarla.

## 1.4 Permisos

| Operación | Roles |
|---|---|
| `POST /clasificaciones`, `POST /clasificaciones/videos` | `tecnico_campo` |
| `GET /modelos/clasificador/dispositivo` y sus archivos | `tecnico_campo` |
| Consultar el trabajo de video | Su solicitante (`spec-trabajos.md`) |
| Publicar una versión del clasificador | `administrador` (endpoint de `spec-prediccion.md`) |

## 1.5 Errores de esta funcionalidad

| HTTP | Código | Mensaje | Cuándo |
|---|---|---|---|
| 400 | `IMAGEN_INVALIDA` | "La imagen no es válida. Envíe una foto JPEG o PNG." | Historia 1, escenario 4; caso borde de megapíxeles |
| 400 | `VIDEO_INVALIDO` | "El video no es válido o dura más de 60 segundos." | Historia 3, escenario 4 |
| 400 | `ARCHIVO_DEMASIADO_GRANDE` | "El archivo supera el tamaño máximo permitido." | Imagen > 10 MB o video > 50 MB |
| 404 | `ARCHIVO_MODELO_NO_ENCONTRADO` | "El archivo del modelo no existe." | Historia 2, escenario 6 |
| 503 | `MODELO_NO_DISPONIBLE` | (de `spec-prediccion.md`) | Sin versión vigente o sin cargar |
| 503 | `DEPENDENCIA_NO_DISPONIBLE` | (común) | Firestore o Cloud Storage no disponibles |

Códigos del `error` de un trabajo `CLASIFICACION_VIDEO` `FALLIDO`: `VIDEO_NO_DISPONIBLE` ("El video ya no está disponible. Envíelo nuevamente."), `MODELO_NO_DISPONIBLE` y los comunes de `spec-trabajos.md`.

## 1.6 Criterios de éxito

- **CE-VIS-01:** los escenarios de las historias 1 a 5 pasan como tests automáticos.
- **CE-VIS-02:** `POST /clasificaciones` con una foto de 4 MB responde en menos de 3 s (RNF-06), medido en el contenedor local con `mem_limit: 3g`.
- **CE-VIS-03:** el archivo TFLite pesa menos de 10 MB y el TF.js menos de 15 MB en total, para que la descarga en datos móviles sea razonable.
- **CE-VIS-04:** la primera versión, entrenada con 50 fotos por clase, tiene F1 macro ≥ 0,70 en el conjunto de prueba. Si no se alcanza, se documenta el valor y se publica con justificación, o se sube `--por-clase` y se reentrena (umbral de referencia; con 90 fotos de prueba en total, la métrica es poco precisa).
- **CE-VIS-08:** `preparar_imagenes --por-clase 50` descarga menos de 3 GB en total y no ocupa más de 500 MB de disco en ningún momento.
- **CE-VIS-05:** un video de 60 s se procesa en menos de 60 s.
- **CE-VIS-06:** `docs/modelos.md` agrega la sección del clasificador: datasets y licencias, etiquetas, preprocesamiento, entrenamiento, métricas por clase, limitaciones y cómo usar los archivos en los dispositivos.
- **CE-VIS-07:** cobertura ≥ 80 % (README D-13), Ruff y mypy sin errores, pipeline en verde.

## 1.7 Supuestos

- Con 600 fotos, el entrenamiento se puede hacer en CPU en un tiempo razonable (del orden de decenas de minutos); con GPU es más rápido. No corre en el pipeline: los tests usan un modelo diminuto.
- Las fotos de PlantVillage se pueden pedir sueltas desde una copia pública del dataset original (por ejemplo, el repositorio de los autores en GitHub), con la licencia CC0 de la publicación en Mendeley Data. La fuente exacta y su licencia se confirman en T02 y se anotan en `fuentes.json`. Si no es posible, se usa el zip de Mendeley (cerca de 1 GB) con el mismo procedimiento de rangos de bytes.
- En WSL2, la carpeta temporal de trabajo puede estar en un disco de Windows (`--temporal /mnt/c/...`), para que lo que se borra libere espacio en Windows de inmediato (el disco virtual de WSL2 no se achica solo).
- El RNF-06 offline (< 5 s en el dispositivo) depende de Flutter y Vue.js. Este servicio solo garantiza un modelo de tamaño apto (CE-VIS-03).
- El gateway reenvía cuerpos grandes en streaming y sin límite propio (`api-gateway/specs/spec-enrutamiento.md`, casos borde).

## 1.8 Aclaraciones

- **AC-01 — ¿Por qué MobileNetV3 Large y no Small?** Large tiene mejor exactitud y sigue cabiendo en el dispositivo cuantizado (unos 5 MB en TFLite con float16). Small se puede evaluar en una versión posterior si el dispositivo no cumple los 5 s.
- **AC-02 — ¿Por qué los modelos se descargan a través de la API y no con URL firmadas de Cloud Storage?** El modelo TF.js son varios archivos que `model.json` referencia con rutas relativas: con una URL firmada por archivo, esas rutas no resuelven. Además, así la descarga pasa por la misma seguridad que el resto y no hace falta configurar CORS en el bucket.
- **AC-03 — ¿Por qué el umbral lo aplican el servidor y los dispositivos, y no el modelo?** Así el modelo exportado es el mismo en los tres lugares, y el umbral se puede cambiar en una versión sin reentrenar.
- **AC-04 — ¿Por qué el video es un trabajo y la foto no?** Una foto se clasifica en menos de un segundo. Un video de 60 s implica decodificarlo y clasificar 30 fotogramas: puede pasar el tiempo límite del gateway (10 s).
- **AC-05 — ¿Por qué una muestra de 50 fotos por clase?** Resuelta (2026-11-04): es un proyecto académico y el costo que importa es el tiempo de descarga (43 GB de ASDID son horas). 50 por clase bajan unos 2,4 GB. Se revisa después de la primera versión: si la exactitud no alcanza, se sube `--por-clase` y se reentrena, sin cambiar nada más.

## 1.9 Fuera de alcance

- Clasificación de sorgo y de plagas o insectos (sin dataset abierto adecuado).
- Detección de objetos o segmentación (solo clasificación de la imagen entera).
- Guardar imágenes para reentrenamiento (la constitución §4 lo permite solo si una spec lo pide; esta no lo pide).
- Clasificación offline: la implementan Flutter y Vue.js.

---

# 2. Plan

Criterio general: lo mínimo que cumple la spec y la constitución. Reutiliza `modelos`, `AlmacenArchivos` y `trabajos`.

**Documentos que debe tener a mano quien implemente:** la constitución, `specs/README.md`, `spec-base.md`, `spec-trabajos.md`, `spec-prediccion.md`, este archivo y `servicio-operaciones/specs/spec-incidencias.md` (formato de `clasificacion`).

## 2.1 Dependencias

| Dependencia | Grupo | Para qué |
|---|---|---|
| `tensorflow-cpu` | Principal | Inferencia con el modelo Keras en el servidor (Linux x86; más liviano que `tensorflow`) |
| `pillow` | Principal | Validación y preparación de imágenes (constitución §2) |
| `opencv-python-headless` | Principal | Lectura de video y extracción de fotogramas (incluye FFmpeg; sin interfaz gráfica) |
| `python-multipart` | Principal | Recepción de archivos en FastAPI |
| `tensorflow`, `tensorflowjs` | Opcional `[ml]` | Entrenamiento con GPU y conversión a TF.js. No van en la imagen de Cloud Run |

El grupo `[ml]` se instala en la máquina de entrenamiento y en el pipeline (para el test de exportación). Si `tensorflowjs` exige otra versión de TensorFlow, se fija la combinación compatible en `pyproject.toml` y se anota aquí.

## 2.2 Configuración

| Variable | Obligatoria | Uso |
|---|---|---|
| `VISION_TAMANIO_MAXIMO_IMAGEN_MB` | No (10) | Límite de imagen; igual al de la foto de una incidencia en `servicio-operaciones` |
| `VISION_TAMANIO_MAXIMO_VIDEO_MB` | No (50) | Límite de video |

El umbral de confianza no es una variable: viaja con cada versión del modelo.

## 2.3 Preparación de imágenes (`app/ml/datos/preparar_imagenes.py`)

`python -m app.ml.datos.preparar_imagenes --por-clase 50 [--semilla 42] [--salida <carpeta>] [--temporal <carpeta>]`:

1. **Fuentes fijas en el script:** las URL de los 8 zips de ASDID en Zenodo (`https://zenodo.org/records/7304859/files/<categoria>.zip?download=1`, sin los `unused_*`) con su MD5 publicado, y la fuente de las 4 clases de maíz de PlantVillage. Una tabla fija asigna cada carpeta de origen a su etiqueta.
2. **Lectura remota de los zips:** un archivo de solo lectura sobre HTTP (`seek`, `tell` y `read` con el header `Range`) se le pasa a `zipfile.ZipFile`, que lee solo el directorio central al final del zip. Se listan las fotos (`.jpg`, `.jpeg`, `.png`) y se eligen `--por-clase` al azar con la semilla. Así se descarga solo lo de cada foto elegida.
3. **Descarga y reducción:** 4 descargas en paralelo. Cada foto se lee en memoria, se corrige la orientación EXIF, se convierte a RGB, se reduce a 256 px por el lado menor y se guarda en JPEG de calidad 90 en `--salida`. El original no toca el disco. Errores de red: 3 reintentos con espera creciente por foto; si falla, se reemplaza por otra foto de la misma clase y se anota.
4. **Retomar:** si la foto reducida ya existe en `--salida` (por nombre de origen), no se descarga de nuevo.
5. **Duplicados:** se descartan fotos con el mismo SHA-256 después de reducir y se reemplazan por otra de la misma clase.
6. **Particiones:** 70/15/15 estratificado por etiqueta con la semilla (35/7/8 fotos por clase con 50).
7. **Salidas:** `datos/imagenes/manifiesto.csv`, `datos/imagenes/fuentes.json` y un resumen por etiqueta y partición, con los bytes descargados.
8. **Subida:** empaqueta `--salida` en un `.tar` y lo sube a `gs://<bucket>/datasets/imagenes/<sha256>.tar` (si ya existe, no lo vuelve a subir).

`--temporal` solo se usa si la fuente de PlantVillage obliga a bajar un zip entero (supuesto de 1.7).

## 2.4 Entrenamiento y exportación (`app/ml/entrenar.py`, opción `clasificador`)

1. Descarga el `.tar` del manifiesto vigente (o usa la carpeta local con `--imagenes`).
2. `tf.keras.utils.set_random_seed(semilla)` y `tf.config.experimental.enable_op_determinism()`.
3. Modelo: `MobileNetV3Large(input_shape=(224, 224, 3), include_top=False, weights="imagenet", include_preprocessing=True)`, `GlobalAveragePooling2D`, `Dropout(0.2)` y `Dense(12, softmax)`.
4. Aumento de datos solo al entrenar (capas `RandomFlip`, `RandomRotation(0.1)`, `RandomZoom(0.1)`, `RandomContrast(0.1)`, `RandomBrightness(0.1)`), recorte aleatorio de 256 a 224; en validación y prueba, recorte central.
5. Fase 1: base congelada, Adam 1e-3, hasta 15 épocas. Fase 2: se descongelan las últimas 30 capas, Adam 1e-5, hasta 15 épocas. Pesos por clase para el desbalance. `EarlyStopping` sobre la pérdida de validación (paciencia 3, restaura los mejores pesos).
6. Métricas sobre la partición de prueba: exactitud, F1 macro, sensibilidad por clase y matriz de confusión. Umbral por defecto 0,50.
7. Exportaciones desde el mismo modelo entrenado:
   - `modelo.keras` (servidor);
   - `tflite/modelo.tflite` con `TFLiteConverter.from_keras_model` y cuantización float16;
   - `tfjs/model.json` y sus archivos de pesos con `tensorflowjs.converters.save_keras_model` → convertidos a *graph model* con cuantización uint8.
8. Verificación antes de registrar (falla si no se cumple): las tres variantes tienen 12 salidas; Keras y TFLite eligen la misma categoría para las imágenes de prueba de `tests/fixtures`.
9. Sube todo a `gs://<bucket>/modelos/clasificador/<version>/` con `etiquetas.json` y `metadatos.json`, calcula tamaños y SHA-256 de cada archivo exportado y registra la `CANDIDATA` (`spec-prediccion.md` 2.5).

## 2.5 Carga en el servidor

`CargadorModelos` (`spec-prediccion.md` 2.6) pasa a tener un cargador por tipo de artefacto: `joblib` para `rendimiento` y `patrones`, `tf.keras.models.load_model` para `clasificador`. Ambos en un hilo. Después de cargar el clasificador, hace una inferencia de calentamiento con una imagen negra para que la primera solicitud no pague la inicialización.

## 2.6 Módulo `vision/`

```text
app/vision/
├── etiquetas.py     # tabla de etiquetas, nombres, cultivos y tipos sugeridos; INDETERMINADO
├── imagenes.py      # validar_imagen(), preparar_imagen(): funciones puras con Pillow
├── clasificador.py  # clasificar(arreglo, modelo_cargado) -> ResultadoClasificacion; umbral; top 3
├── video.py         # validar_video(), extraer_fotogramas(): OpenCV
├── servicio.py      # clasificar_imagen(), solicitar_video(), manejador del trabajo
├── esquemas.py
└── router.py
```

- **`imagenes.py`:**
  - `validar_imagen(datos: bytes)`: `Image.open` (sin decodificar del todo) comprueba que el formato sea JPEG o PNG y que el tamaño en píxeles esté entre 64 × 64 y 40 megapíxeles; luego `load()` dentro de un `try` detecta imágenes dañadas. `Image.MAX_IMAGE_PIXELS` se fija en 40 millones.
  - `preparar_imagen(imagen) -> np.ndarray`: `ImageOps.exif_transpose`, RGB, reducir a 256 por el lado menor, recorte central de 224 × 224 y `float32` de 0 a 255 (la normalización la hace el modelo). Es el mismo preprocesamiento de validación del entrenamiento y el que se documenta para los dispositivos.
- **`clasificador.py`:** `predict` sobre un lote de 1, orden de probabilidades, `INDETERMINADO` si la mayor es menor que el umbral, 3 alternativas, confianza con 4 decimales (mitad hacia arriba). Con lotes de hasta 30 para el video.
- **`video.py`:**
  - `validar_video(ruta)`: `cv2.VideoCapture` abre el archivo; duración = cantidad de fotogramas ÷ FPS; > 60 s o sin fotogramas → `VIDEO_INVALIDO`.
  - `extraer_fotogramas(ruta, maximo=30)`: posiciones uniformes (`CAP_PROP_POS_FRAMES`), conversión BGR → RGB y el mismo `preparar_imagen`.
- **Recepción de archivos:** `UploadFile` leído por bloques; se corta al pasar el límite (`ARCHIVO_DEMASIADO_GRANDE`), sin cargar más de lo permitido en memoria. El video se escribe a un archivo temporal para validarlo con OpenCV, se sube a `gs://<bucket>/temporales/videos/<idTrabajo>` y se borra el archivo local.
- **`servicio.py`:**
  - `clasificar_imagen(datos, solicitante)`: valida, prepara, clasifica en un hilo (`asyncio.to_thread`), guarda en `clasificaciones` con `sha256Imagen` y `fechaExpiracion` (90 días), y responde.
  - `solicitar_video(archivo, solicitante)`: valida, sube a temporales y crea el trabajo (`spec-trabajos.md`) con `parametros = { rutaVideo }`.
  - Manejador `CLASIFICACION_VIDEO` (registrado en `crear_app()` con tiempo límite de 3 minutos): descarga a un archivo temporal, extrae, clasifica en un hilo, agrega (probabilidad promedio por categoría entre los fotogramas que no son `INDETERMINADO`; si todos lo son, `INDETERMINADO`) y en un `finally` borra el video de GCS y el archivo local.
- El bucket tiene una regla de ciclo de vida que borra `temporales/` a 1 día, por si un borrado falla. Se documenta para GCP; el emulador no la aplica.

## 2.7 Descarga para dispositivos (en `modelos/router.py`)

- `GET /modelos/clasificador/dispositivo`: lee la vigente de `versiones_modelo` y arma la respuesta de 2.8. Las rutas de descarga son relativas al prefijo de la API.
- `GET /modelos/clasificador/dispositivo/archivos/{ruta:path}`: solo acepta rutas que están en `exportaciones` de la vigente (evita recorrer el bucket con `..`). Compara `If-None-Match` con el SHA-256 y responde `304`, o descarga de GCS y responde en streaming con `Content-Type` (`application/octet-stream` para `.tflite` y `.bin`, `application/json` para `model.json`), `Content-Length`, `ETag` y `Cache-Control`.

## 2.8 Endpoints

Prefijo `/api/ia/v1`.

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /clasificaciones` (`multipart/form-data`, campo `imagen`) | `tecnico_campo` | `201` + clasificación | 400 `IMAGEN_INVALIDA`, `ARCHIVO_DEMASIADO_GRANDE` o `DATOS_INVALIDOS`, 401, 403, 503 `MODELO_NO_DISPONIBLE` o `DEPENDENCIA_NO_DISPONIBLE` |
| `POST /clasificaciones/videos` (`multipart/form-data`, campo `video`) | `tecnico_campo` | `202` + trabajo (`spec-trabajos.md`) | 400 `VIDEO_INVALIDO`, `ARCHIVO_DEMASIADO_GRANDE` o `DATOS_INVALIDOS`, 401, 403, 503 |
| `GET /modelos/clasificador/dispositivo` | `tecnico_campo` | `200` + metadatos | 401, 403, 503 `MODELO_NO_DISPONIBLE` |
| `GET /modelos/clasificador/dispositivo/archivos/{ruta}` | `tecnico_campo` | `200` + archivo, o `304` | 401, 403, 404 `ARCHIVO_MODELO_NO_ENCONTRADO`, 503 |

**Respuesta de clasificación:**

```json
{
  "id": "uuid",
  "fecha": "2026-11-04T12:00:00Z",
  "categoria": "SOYA_ROYA",
  "nombre": "Roya asiática de la soya",
  "cultivo": "SOYA",
  "tipoIncidenciaSugerido": "ENFERMEDAD",
  "confianza": "0.8731",
  "alternativas": [
    { "categoria": "SOYA_MANCHA_DIANA", "nombre": "Mancha diana", "confianza": "0.0712" },
    { "categoria": "SOYA_TIZON_CERCOSPORA", "nombre": "Tizón por Cercospora", "confianza": "0.0301" }
  ],
  "clasificacion": {
    "categoria": "SOYA_ROYA",
    "confianza": "0.8731",
    "versionModelo": "clasificador-1",
    "origen": "SERVIDOR"
  },
  "versionModelo": { "nombre": "clasificador", "version": 1 },
  "orientativo": true,
  "aviso": "Clasificación orientativa. No sustituye una evaluación técnica agrícola."
}
```

`alternativas` lista las otras dos de las 3 más probables. Si `categoria = INDETERMINADO`, `nombre`, `cultivo` y `tipoIncidenciaSugerido` corresponden a esa categoría (cultivo y tipo nulos) y `alternativas` trae las 3 más probables.

**Metadatos para dispositivos:**

```json
{
  "versionModelo": "clasificador-1",
  "version": 1,
  "fechaPublicacion": "2026-11-04T12:00:00Z",
  "umbral": "0.50",
  "entrada": { "alto": 224, "ancho": 224, "canales": "RGB", "rango": "0-255", "recorte": "central tras reducir a 256 por el lado menor" },
  "etiquetas": [
    { "indice": 0, "categoria": "MAIZ_MANCHA_GRIS", "nombre": "Mancha gris de la hoja", "cultivo": "MAIZ", "tipoIncidenciaSugerido": "ENFERMEDAD" }
  ],
  "exportaciones": {
    "tflite": { "archivos": [ { "ruta": "/api/ia/v1/modelos/clasificador/dispositivo/archivos/tflite/modelo.tflite", "tamanio": 5412345, "sha256": "..." } ] },
    "tfjs": { "archivos": [ { "ruta": "/api/ia/v1/modelos/clasificador/dispositivo/archivos/tfjs/model.json", "tamanio": 120345, "sha256": "..." } ] }
  }
}
```

`versionModelo` (texto) es el mismo valor que lleva la `clasificacion` de una incidencia y cabe en los 50 caracteres que acepta `servicio-operaciones`.

**Resultado del trabajo de video:**

```json
{
  "categoriaPredominante": "SOYA_ROYA",
  "nombre": "Roya asiática de la soya",
  "confianza": "0.7810",
  "clasificacion": { "categoria": "SOYA_ROYA", "confianza": "0.7810", "versionModelo": "clasificador-1", "origen": "SERVIDOR" },
  "resumen": [ { "categoria": "SOYA_ROYA", "fotogramasPrincipal": 21, "confianzaPromedio": "0.7810" } ],
  "fotogramas": [ { "segundo": "0.00", "categoria": "SOYA_ROYA", "confianza": "0.8120" } ],
  "duracionSegundos": "42.50",
  "versionModelo": { "nombre": "clasificador", "version": 1 },
  "orientativo": true,
  "aviso": "Clasificación orientativa. No sustituye una evaluación técnica agrícola."
}
```

## 2.9 Empaquetado

- `Dockerfile` del servicio: agrega `libglib2.0-0` (OpenCV headless). WeasyPrint sigue para `spec-reportes.md`.
- La imagen de desarrollo `docker/fastapi` ya trae esas librerías.
- La primera instalación de `tensorflow-cpu` en el volumen `ia-venv` tarda varios minutos; el `start_period` del `healthcheck` (120 s) se sube a 300 s.

## 2.10 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `tests/unit/vision/test_imagenes.py` | Formatos por contenido, imagen dañada, tamaño mínimo, megapíxeles, EXIF, transparencia y grises |
| Unitario | `tests/unit/vision/test_clasificador.py` | Umbral e `INDETERMINADO`, top 3, redondeo de la confianza, con un modelo simulado que devuelve probabilidades fijas |
| Unitario | `tests/unit/vision/test_video.py` | Con `tests/fixtures/video_5s.mp4` y uno de 61 s generado en el test: duración, 30 fotogramas como máximo, posiciones uniformes, archivo que no es video |
| Unitario | `tests/unit/vision/test_manejador_video.py` | Agregación, todos `INDETERMINADO`, borrado del video en éxito y en error, `VIDEO_NO_DISPONIBLE` |
| Unitario | `tests/unit/ml/test_preparar_imagenes.py` | Con zips pequeños que imitan ASDID servidos por un servidor HTTP local con soporte de `Range`: solo se piden los rangos de las fotos elegidas, correspondencia de etiquetas, reducción, retomar sin volver a descargar, reemplazo de duplicados y de fallas, particiones estratificadas y reproducibles con la misma semilla |
| Integración | `tests/integration/ml/test_exportacion_clasificador.py` | Entrena 1 época un modelo diminuto sobre `tests/fixtures/imagenes` (misma cabeza y exportaciones), exporta las tres variantes y verifica etiquetas, cantidad de salidas y misma categoría en Keras y TFLite (Historia 2, escenario 5; constitución §8). Requiere el grupo `[ml]` |
| Integración | `tests/integration/vision/test_router_vision.py` | Endpoints con el modelo diminuto publicado en los emuladores: Historia 1 completa, Historia 2 (`ETag`, `304`, ruta ajena → 404), Historia 3 de punta a punta con RabbitMQ, permisos y OpenAPI |
| Integración | `tests/integration/vision/test_rendimiento_vision.py` | CE-VIS-02 con una foto de 4 MB |

Las imágenes de `tests/fixtures/imagenes` son unas pocas por etiqueta, tomadas del conjunto preparado (CC0), reducidas a 256 px.

---

# 3. Tareas

Cada tarea se da por terminada solo con sus tests en verde. Las marcadas con **[P]** pueden hacerse en paralelo con la anterior.

- [ ] **T01** — Agregar las dependencias y variables de 2.1 y 2.2, y `vision/etiquetas.py`. *Hecho cuando:* `pip install -e ".[dev,ml]"` funciona y se fija la combinación de `tensorflow` y `tensorflowjs`.
- [ ] **T02** — Implementar `app/ml/datos/preparar_imagenes.py` con la lectura remota de los zips. Confirmar la fuente y la licencia de PlantVillage. Ejecutarlo con `--por-clase 50` (puede correr de fondo mientras se avanza con T03), versionar `manifiesto.csv` y `fuentes.json`, y subir el `.tar`. Crear `tests/fixtures/imagenes`. *Hecho cuando:* pasa `test_preparar_imagenes.py`, el resumen muestra 50 fotos en cada una de las 12 etiquetas y se cumple CE-VIS-08.
- [ ] **T03** — Implementar `vision/imagenes.py` y `vision/clasificador.py`. *Hecho cuando:* pasan `test_imagenes.py` y `test_clasificador.py`.
- [ ] **T04** — Agregar `clasificador` a `app/ml/entrenar.py` con las exportaciones y la verificación, y el cargador Keras en `CargadorModelos`. *Hecho cuando:* pasa `test_exportacion_clasificador.py`.
- [ ] **T05** — Implementar `POST /clasificaciones` y la descarga para dispositivos. *Hecho cuando:* pasan las historias 1 y 2 de `test_router_vision.py`.
- [ ] **T06** — Implementar `vision/video.py`, `POST /clasificaciones/videos` y el manejador `CLASIFICACION_VIDEO`. *Hecho cuando:* pasan `test_video.py`, `test_manejador_video.py` y la Historia 3 de `test_router_vision.py`.
- [ ] **T07** [P] — Ajustar el `Dockerfile`, el `healthcheck` de Docker Compose y el pipeline (grupo `[ml]`). *Hecho cuando:* el pipeline corre en verde y se cumple CE-VIS-02 con `test_rendimiento_vision.py`.
- [ ] **T08** — Entrenar la versión 1 del clasificador (CPU o GPU), publicarla y agregar su sección a `docs/modelos.md`. *Hecho cuando:* se cumplen CE-VIS-03 a CE-VIS-06 y una foto de `tests/fixtures` se clasifica a través del gateway con un token de `tecnico.prueba`; se anota el resultado en esta tarea.
