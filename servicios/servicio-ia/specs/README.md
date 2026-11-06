# Specs — `servicio-ia`

Un archivo por funcionalidad, cada uno con tres partes: **Spec** (qué hace), **Plan** (cómo se construye) y **Tareas** (en qué orden se implementa).

- Constitución de referencia: `servicio-ia` v4.0.0 (2026-11-04). Si un archivo la contradice, prevalece la constitución.
- Documento de requisitos: `SW2_Parcial_2.pdf` (CU, RF, RN y RNF).
- Criterio: lo más simple que cumpla el documento de requisitos y la constitución. Es un proyecto de examen, no un sistema en producción.

## Cómo usar estos archivos

Quien implemente (persona o agente) necesita tres cosas en el repositorio: la constitución (`servicios/servicio-ia/Constitucion.md`), este README y el archivo de la funcionalidad. Las funcionalidades se implementan en el orden del índice; cada una se termina con sus tests en verde antes de pasar a la siguiente.

Los demás servicios, el API Gateway y el realm de Keycloak ya están implementados. Antes de escribir un cliente o una herramienta MCP se revisa el contrato real del servicio consultado (su `specs/` y su OpenAPI), no se supone.

## Índice y orden de implementación

| Orden | ID | Archivo | Funcionalidad | Prioridad | CU | RF |
|---|---|---|---|---|---|---|
| 1 | 001 | [spec-base.md](spec-base.md) | Base del servicio: seguridad, errores, correlación, salud, consulta a microservicios | Soporte | — | — |
| 2 | 002 | [spec-trabajos.md](spec-trabajos.md) | Trabajos asíncronos: Firestore, cola, consumidor, estados | Soporte | CU-16, CU-17, CU-18, CU-25 | RF-22, RF-23, RF-24 |
| 3 | 003 | [spec-prediccion.md](spec-prediccion.md) | Versionado de modelos, conjunto de referencia público, rendimiento, agrupación y anomalías | Baja | CU-14, CU-15 | RF-18, RF-19 |
| 4 | 004 | [spec-vision.md](spec-vision.md) | Clasificación de imágenes (MobileNetV3) y video, exportación TFLite y TF.js | Media | CU-16 | RF-20, RF-21, RF-22 |
| 5 | 005 | [spec-agentes.md](spec-agentes.md) | Herramientas MCP de solo lectura, agentes LangGraph con Ollama y verificación de cifras | Baja | CU-17 | RF-23 |
| 6 | 006 | [spec-reportes.md](spec-reportes.md) | Reportes por texto o voz (Whisper), catálogo fijo, PDF, Excel y CSV, reportes programados para n8n | Baja | CU-18, CU-25 | RF-24, RF-25, RF-34 |

- La prioridad de los casos de uso sale de la sección 3.6.3 del documento de requisitos. Las specs de soporte van primero porque las demás las usan.

## Mapa de colecciones y artefactos

| Ubicación | Nombre | Archivo |
|---|---|---|
| Firestore | Colección `trabajos` (TTL sobre `fechaExpiracion`) | spec-trabajos.md |
| RabbitMQ | Cola `servicio-ia.trabajos` y su DLQ `servicio-ia.trabajos.dlq` | spec-trabajos.md |
| Firestore | Colecciones `versiones_modelo`, `predicciones` y `analisis` | spec-prediccion.md |
| Cloud Storage | `modelos/<nombre>/<version>/` (`modelo.joblib`, `dataset.csv`, `metadatos.json`) | spec-prediccion.md |
| Repositorio | `datos/referencia/` (conjunto de referencia del USDA ERS, fuentes e IPC) y `docs/modelos.md` | spec-prediccion.md |
| Firestore | Colección `clasificaciones` (TTL de 90 días sobre `fechaExpiracion`) | spec-vision.md |
| Cloud Storage | `modelos/clasificador/<version>/` (`modelo.keras`, `tflite/`, `tfjs/`), `datasets/imagenes/<sha256>.tar` y `temporales/videos/` (ciclo de vida de 1 día) | spec-vision.md |
| Repositorio | `datos/imagenes/` (manifiesto y fuentes de ASDID y PlantVillage; sin las imágenes) | spec-vision.md |
| Cloud Storage | `reportes/<idTrabajo>/` (ciclo de vida de 7 días) y `temporales/audios/` | spec-reportes.md |
| RabbitMQ | Exchange `eventos` (topic, durable), routing key `ia.reporte.completado` (evento `ReporteCompletado`, salida) | spec-reportes.md |

## Mapa de endpoints

Prefijo `/api/ia/v1`. Se completa con cada spec.

| Ruta | Métodos | Archivo |
|---|---|---|
| `/trabajos/{id}` | `GET` | spec-trabajos.md |
| `/predicciones` | `POST`, `GET` | spec-prediccion.md |
| `/analisis`, `/analisis/{id}` | `POST`, `GET` | spec-prediccion.md |
| `/modelos` | `GET` | spec-prediccion.md |
| `/modelos/{nombre}/versiones/{version}/publicacion` | `POST` | spec-prediccion.md |
| `/clasificaciones` | `POST` | spec-vision.md |
| `/clasificaciones/videos` | `POST` | spec-vision.md |
| `/modelos/clasificador/dispositivo`, `/modelos/clasificador/dispositivo/archivos/{ruta}` | `GET` | spec-vision.md |
| `/consultas-agente` | `POST` | spec-agentes.md |
| `/mcp` | MCP (*streamable HTTP*) | spec-agentes.md |
| `/reportes` | `POST` | spec-reportes.md |
| `/reportes/voz` | `POST` | spec-reportes.md |
| `/reportes/{idTrabajo}/archivos/{formato}` | `GET` | spec-reportes.md |

Fuera del prefijo, sin token: `/salud`, `/salud/liveness`, `/salud/readiness`, `/openapi.json` y `/docs` (spec-base.md).

## Decisiones transversales

| ID | Decisión |
|---|---|
| D-01 | **Python 3.12**, la versión de la imagen de desarrollo `docker/fastapi` (cumple "3.11+" de la constitución §2). `requires-python = ">=3.12,<3.13"`. |
| D-02 | **Dependencias por spec:** cada spec agrega solo las librerías que usa (TensorFlow, scikit-learn, LangGraph, Whisper, WeasyPrint…). La base no las instala, para que la imagen y la memoria crezcan solo cuando hace falta (`mem_limit: 3g` en Docker Compose). |
| D-03 | **Decimales en JSON:** solo texto con punto decimal (`"820.50"`), en la entrada y en la salida. Un número JSON en un campo decimal de entrada se rechaza con `400 DATOS_INVALIDOS`. Los decimales que llegan de otros servicios como texto se convierten a `Decimal` al leerlos (constitución, enmienda 2.1.0); nunca a `float` antes de validarlos. Los modelos de ML pueden trabajar en `float` internamente; el resultado vuelve a `Decimal` y texto al responder. |
| D-04 | **Fechas:** con hora en ISO 8601 UTC con `Z` (`2026-11-04T14:00:00Z`); sin hora como `AAAA-MM-DD`. |
| D-05 | **Identificadores:** UUID v4 en minúsculas, generados por este servicio. |
| D-06 | **JSON en camelCase:** todos los esquemas heredan de `ModeloBase` (alias camelCase, `populate_by_name`); los de entrada además prohíben campos desconocidos. El código Python usa snake_case (constitución §13). |
| D-07 | **Roles:** `administrador`, `gerencia` y `tecnico_campo` para usuarios. `lectura_ia` para la cuenta de servicio de GraphQL (lectura de predicciones y análisis, spec-prediccion.md) y `reportes_ia` para la de n8n (reportes programados, spec-reportes.md). Los roles nuevos se agregan al realm (`docker/keycloak/realms/realm-agro.json` y `specs/spec-keycloak-realm.md`). La cuenta de servicio propia (`servicio-ia`) ya tiene `lectura_gestion`, `lectura_inventario` y `lectura_operaciones`. |
| D-08 | **Consulta a otros microservicios:** siempre `GET {API_GATEWAY_URL}/api/<servicio>/v1/...` con token de cuenta de servicio (client credentials contra `KEYCLOAK_TOKEN_URL`, en caché hasta 30 s antes de vencer), tiempo límite por llamada (5 s por defecto) y un solo intento. Única excepción: un `401` renueva el token y repite una vez. El cliente solo expone lecturas (RN-14). |
| D-09 | **Correlación:** `X-Correlation-Id` con el mismo formato que el gateway (`[A-Za-z0-9-]{1,64}`); si falta o no coincide, se genera un UUID. Se propaga a las respuestas, a las llamadas al gateway y, desde `spec-trabajos.md`, a los mensajes y trabajos. |
| D-10 | **Logs:** JSON de una línea por registro en la salida estándar, con `fecha`, `nivel`, `logger`, `mensaje`, `idCorrelacion` y campos extra. Un log de acceso por solicitud propio (el de uvicorn se desactiva). Nunca tokens, secretos ni nombres; solo el `sub`. |
| D-11 | **Variables de entorno:** las de `docker-compose.yml`. Se leen con `pydantic-settings` en `app/config.py`; si falta una obligatoria, el proceso no arranca. Cada spec agrega las suyas. |
| D-12 | **Tests:** unitarios sin red ni contenedores (dobles de los `Protocol` de `integracion`, `httpx.MockTransport` para HTTP, tokens firmados con una clave RSA local). Los de integración levantan la aplicación con el `TestClient` de FastAPI; desde `spec-trabajos.md` usan además los emuladores de Firestore y GCS y RabbitMQ de Docker Compose (en GitHub Actions, como contenedores de servicio). |
| D-13 | **Cobertura:** `pytest-cov` sobre `app`, excluyendo `app/integracion` y `app/ml` (constitución §8). Incluye `comun`, `config` y `main` además de los módulos de capacidad: es más estricto que el mínimo de la constitución. Umbral 80 %. |
| D-14 | **OpenAPI:** lo genera FastAPI desde el código (`/openapi.json`, `/docs`). Cada ruta declara sus respuestas de error con `RespuestaError`; un test falla si una ruta del prefijo no documenta las suyas. |
| D-15 | **Cola de trabajos:** `servicio-ia.trabajos` (durable, dead-letter al exchange por defecto con routing key `servicio-ia.trabajos.dlq`) y `servicio-ia.trabajos.dlq` (durable). Reintentos de infraestructura en el propio proceso: 3, con espera de 1 s, 2 s y 4 s; agotados, `nack` sin reencolar. Misma convención que inventario (D-11, D-12) y operaciones (D-13, D-14). |
| D-16 | **Consumidor en el mismo proceso que la API**, con `prefetch` = `TRABAJOS_CONCURRENCIA`, para no cargar los modelos dos veces (spec-trabajos.md AC-01). En Cloud Run: instancia mínima 1 y CPU siempre asignada. |
| D-17 | **Paginación de listados:** `pagina` (desde 0) y `tamanio` (por defecto 20, máximo 100); respuesta `{ items, pagina, tamanio, total }`, igual que `servicio-gestion`. |
| D-18 | **Datos de entrenamiento:** conjunto de referencia público (USDA ERS, maíz, soya y sorgo, convertido a BOB/ha y kg/ha) más las campañas finalizadas de `servicio-gestion` cuando existan (spec-prediccion.md 1.1). Toda versión guarda el conjunto exacto usado. |
| D-19 | **Archivos recibidos:** se validan por su contenido, no por extensión ni `Content-Type`, y se leen por bloques cortando al pasar el límite. Imágenes y videos no se conservan; solo el SHA-256 de la imagen (spec-vision.md). |
| D-20 | **Modelo de lenguaje:** Ollama con `OLLAMA_MODEL` (`qwen2.5:3b`), temperatura 0, detrás del `Protocol ModeloLenguaje`; sin LangChain. Toda cifra de un texto generado se verifica contra los datos consultados y la oración que no se puede verificar se quita (spec-agentes.md 2.6). Lo reutiliza `spec-reportes.md`. |

## Catálogo de códigos de error

| HTTP | Código | Archivo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Todos |
| 400 | `IMAGEN_INVALIDA` | visión |
| 400 | `VIDEO_INVALIDO` | visión |
| 400 | `ARCHIVO_DEMASIADO_GRANDE` | visión, reportes (audio) |
| 400 | `AUDIO_INVALIDO` | reportes |
| 401 | `NO_AUTENTICADO` | Todos |
| 403 | `SIN_PERMISO` | Todos |
| 404 | `RECURSO_NO_ENCONTRADO` | Todos (ruta inexistente) |
| 404 | `TRABAJO_NO_ENCONTRADO` | trabajos |
| 404 | `CAMPANIA_NO_ENCONTRADA` | predicción (lo reporta `servicio-gestion`) |
| 404 | `ANALISIS_NO_ENCONTRADO` | predicción |
| 404 | `VERSION_MODELO_NO_ENCONTRADA` | predicción (modelos) |
| 404 | `ARCHIVO_MODELO_NO_ENCONTRADO` | visión |
| 404 | `REPORTE_NO_ENCONTRADO` | reportes |
| 404 | `REPORTE_EXPIRADO` | reportes |
| 405 | `METODO_NO_PERMITIDO` | Todos |
| 409 | `VERSION_NO_PUBLICABLE` | predicción (modelos) |
| 409 | `REPORTE_EN_PROCESO` | reportes |
| 422 | `DATOS_INSUFICIENTES` | predicción |
| 422 | `CULTIVO_NO_SOPORTADO` | predicción |
| 422 | `METRICAS_INFERIORES` | predicción (modelos) |
| 500 | `ERROR_INTERNO` | Todos (sin exponer detalles) |
| 503 | `AUTENTICACION_NO_DISPONIBLE` | Todos (no se pueden obtener las claves de Keycloak) |
| 503 | `MODELO_NO_DISPONIBLE` | predicción, visión |
| 503 | `MODELO_LENGUAJE_NO_DISPONIBLE` | agentes, reportes |
| 503 | `DEPENDENCIA_NO_DISPONIBLE` | Los que consultan otros microservicios, Firestore o RabbitMQ |

Códigos del campo `error` de un trabajo `FALLIDO` (no son HTTP): `TIEMPO_AGOTADO`, `TRABAJO_NO_PROCESADO`, `COLA_NO_DISPONIBLE`, `ERROR_INTERNO` (spec-trabajos.md), `VIDEO_NO_DISPONIBLE` y `MODELO_NO_DISPONIBLE` (spec-vision.md), `MODELO_LENGUAJE_NO_DISPONIBLE` y `LIMITE_PASOS_AGENTE` (spec-agentes.md), `REPORTE_NO_SOPORTADO`, `CAMPANIA_NO_IDENTIFICADA`, `AUDIO_SIN_VOZ`, `TRANSCRIPTOR_NO_DISPONIBLE` y `EVENTO_NO_PUBLICADO` (spec-reportes.md) y los de cada manejador (en su spec).

Criterio: `400` para formato (lo valida el esquema Pydantic); `422` para reglas propias del servicio (por ejemplo, datos insuficientes para estimar).

## Matriz de trazabilidad

| Requisito | Descripción resumida | Archivos |
|---|---|---|
| RF-18 | Estimación de rendimiento con Random Forest | predicción |
| RF-19 | Agrupaciones y anomalías con K-Means e Isolation Forest | predicción |
| RF-20 | Clasificación de imágenes con MobileNetV3 en el servidor | visión |
| RF-21 | Modelos exportados para clasificar sin conexión | visión |
| RF-22 | Clasificación de fotogramas de video | visión, trabajos |
| RNF-06 | Clasificación en el servidor en menos de 3 s | visión |
| RF-23 | Agentes LangGraph con herramientas MCP y Ollama | agentes, reportes (agente de reportes) |
| RF-24 | Reportes por voz (Faster-Whisper) o texto, asíncronos con polling | reportes, trabajos |
| RF-25 | Exportación en PDF y Excel (más CSV) | reportes |
| RF-34 | Reportes programados para n8n | reportes (solicitud estructurada, evento `ia.reporte.completado`) |
| RN-13 | Resultados orientativos | predicción, todos los de IA |
| RN-14 | Los agentes y el servicio solo consultan; el modelo de lenguaje no genera cifras | base (cliente de solo lectura), agentes (herramientas de lectura, verificación de cifras) |
| RN-16 | Permisos verificados en el servidor | base, todos |
| RNF-02 | Validación del JWT en cada solicitud | base |
| RNF-03 | Secretos por variables de entorno | base |
| RNF-05 | Consultas REST en menos de 3 s | predicción |
| RNF-08 | La caída de otro servicio no tumba este | base, trabajos, predicción, agentes (Ollama informativo) |
| RNF-11 | Mensajes fallidos en Dead Letter Queue | trabajos |
| RNF-18 | OpenAPI | base, todos |
| RNF-19, RNF-20 | Docker Compose y pipeline propio | base, trabajos |
| RNF-22 | Correlación | base, trabajos |

Se completa con cada spec.

## Diferencias intencionales con el documento de requisitos

Donde difieren, prevalece la constitución.

| Documento de requisitos | Specs y constitución | Motivo |
|---|---|---|
| No menciona base de datos para el servicio de IA | Firestore (trabajos y resultados) y Cloud Storage (modelos y reportes) | Constitución §2 y §4; ambos en GCP, donde se despliega el servicio |
| RF-25 pide PDF y Excel | PDF, Excel y CSV | Pedido del usuario (2026-11-04); CSV sin dependencias nuevas (constitución v4.0.0) |
| Proceso 8: "el agente interpreta la solicitud" (libre) | Catálogo fijo de 5 tipos de reporte; el modelo elige tipo y filtros | Con un reporte libre el modelo decidiría columnas y cálculos, que RN-14 prohíbe |
| Archivos de audio `.wav` y `.mp3` (§1.7.3) | También WebM y OGG | La MediaRecorder API de Chrome y Edge graba en WebM con Opus |
| RNF-17 asigna arquitectura a tres servicios | Módulos por capacidad | Constitución v3.0.0 §3: el servicio casi no tiene lógica de negocio |
| El modelo supervisado se entrena "con datos históricos de campañas proporcionados por Spring Boot" (proceso 9) | Conjunto de referencia público (USDA ERS) más los históricos de `servicio-gestion` cuando existan | El sistema empieza sin campañas finalizadas; sin la referencia no habría modelo |
| K-Means e Isolation Forest "sobre los datos de parcelas y campañas" (proceso 10) | Entrenados sobre la referencia y aplicados a las campañas finalizadas del sistema | Con pocas campañas, agrupar solo entre ellas no tiene sentido (spec-prediccion.md AC-03) |

## Historial de decisiones (2026-11-04)

- Arquitectura por módulos de capacidad (constitución v3.0.0).
- La base del servicio va en su propia spec, sin funcionalidad de negocio, porque la usan las cinco siguientes.
- Trabajos: idempotencia por estado (transición condicional `EN_COLA → PROCESANDO`), sin reintentar manejadores, cierre de trabajos atascados a los 10 minutos (`EN_COLA`) o al pasar su `fechaLimite` (`PROCESANDO`), y solo el solicitante consulta su trabajo.
- Dataset público: USDA ERS Commodity Costs and Returns (maíz, soya y sorgo, con costos por categoría). Se descartaron los de Kaggle (variables que el sistema no tiene, o sintéticos) y ANAPO (sin dataset descargable). Sin calibración a Bolivia; la limitación se documenta (RN-13).
- Implementación de spec-prediccion.md (2026-11-05): conjunto de referencia de 485 filas (IPC desde la API del BLS); artefactos en `modelos/<nombre>/<idEntrenamiento>/`; Firestore y Cloud Storage siempre detrás de `integracion/` (también `DatosAgricolas`); el cultivo se reconoce también por la primera palabra del nombre ("Soya Munasqa"); `lectura_ia` aplicado al realm sin borrarlo.
- Constitución v3.1.0: `modelos` se puede usar desde cualquier módulo y `ml/` puede importar los módulos de capacidad.
- Rol de realm `lectura_ia` para la cuenta de servicio de GraphQL.
- Clasificador: ASDID (soya, CC0) y las clases de maíz de PlantVillage (CC0), 12 etiquetas más `INDETERMINADO` por umbral; sin sorgo (no hay dataset abierto). MobileNetV3 Large con exportaciones TFLite (float16) y TF.js (uint8) de la misma versión. Muestra de 50 fotos por clase, pedidas sueltas dentro de los zips de Zenodo con rangos de bytes (unos 2,4 GB en lugar de 43 GB); se revisa después de la primera versión. Los modelos para dispositivos se descargan a través de la API, no con URL firmadas.
- Agentes: grafo con clasificación (`campanias`, `inventario`, `fuera_de_alcance`) en lugar de un solo agente con todas las herramientas (modelo de 3B); herramientas por MCP también dentro del proceso (transporte en memoria) y publicadas en `/api/ia/v1/mcp` para `gerencia`; oraciones con cifras sin respaldo se quitan; sin historial de conversación.
- Reportes: catálogo fijo de 5 tipos (`CAMPANIAS_FINALIZADAS`, `COSTOS_CAMPANIA`, `INVENTARIO`, `LABORES`, `INCIDENCIAS`); formatos PDF, Excel y CSV; sin sumas ni promedios propios (RN-14); solicitud estructurada para n8n, que funciona sin Ollama (sin resumen); evento `ia.reporte.completado` para todos los reportes, con `origen`; archivos por 7 días.
- Implementación de spec-agentes.md (2026-11-05): MCP SDK 2.x (`MCPServer`); las herramientas exigen el filtro obligatorio de labores e incidencias; 16 pasos del grafo para que se puedan alcanzar las 6 llamadas; el largo de las listas cuenta como cifra respaldada; `/api/ia/v1/mcp` registrado como ruta exacta, con `validar_token` compartido.
- Constitución v4.0.0: descarga de reportes a través de la API en lugar de URL firmadas.
- Implementación de spec-vision.md (2026-11-05): clasificador v1 con F1 macro 0,893 sobre 50 fotos por clase (1.777,5 MB descargados); TF.js se convierte desde un SavedModel con `tensorflowjs` instalado sin dependencias; el entrenamiento del clasificador corre fuera del contenedor del servicio (memoria); la publicación de una versión carga el modelo en segundo plano (el clasificador tarda unos 14 s y el gateway corta a los 10 s).
- `DEPENDENCIA_NO_DISPONIBLE` en lugar de reutilizar `SERVICIO_NO_DISPONIBLE`, que es el código del gateway cuando este servicio está caído: así el cliente distingue "IA no responde" de "IA no pudo obtener los datos".
