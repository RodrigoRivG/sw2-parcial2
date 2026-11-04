# Specs — `servicio-ia`

Un archivo por funcionalidad, cada uno con tres partes: **Spec** (qué hace), **Plan** (cómo se construye) y **Tareas** (en qué orden se implementa).

- Constitución de referencia: `servicio-ia` v3.0.0 (2026-11-04). Si un archivo la contradice, prevalece la constitución.
- Documento de requisitos: `SW2_Parcial_2.pdf` (CU, RF, RN y RNF).
- Criterio: lo más simple que cumpla el documento de requisitos y la constitución. Es un proyecto de examen, no un sistema en producción.

## Cómo usar estos archivos

Quien implemente (persona o agente) necesita tres cosas en el repositorio: la constitución (`servicios/servicio-ia/Constitucion.md`), este README y el archivo de la funcionalidad. Las funcionalidades se implementan en el orden del índice; cada una se termina con sus tests en verde antes de pasar a la siguiente.

Los demás servicios, el API Gateway y el realm de Keycloak ya están implementados. Antes de escribir un cliente o una herramienta MCP se revisa el contrato real del servicio consultado (su `specs/` y su OpenAPI), no se supone.

## Índice y orden de implementación

| Orden | ID | Archivo | Funcionalidad | Prioridad | CU | RF |
|---|---|---|---|---|---|---|
| 1 | 001 | [spec-base.md](spec-base.md) | Base del servicio: seguridad, errores, correlación, salud, consulta a microservicios | Soporte | — | — |
| 2 | 002 | `spec-trabajos.md` (pendiente) | Trabajos asíncronos: Firestore, cola, worker, estados | Soporte | CU-17, CU-18 | RF-24 |
| 3 | 003 | `spec-prediccion.md` (pendiente) | Versionado de modelos, rendimiento, agrupación y anomalías | Baja | CU-14, CU-15 | RF-18, RF-19 |
| 4 | 004 | `spec-vision.md` (pendiente) | Clasificación de imágenes y video, exportación al dispositivo | Media | CU-16 | RF-20, RF-21, RF-22 |
| 5 | 005 | `spec-agentes.md` (pendiente) | Herramientas MCP y agentes LangGraph | Baja | CU-17 | RF-23 |
| 6 | 006 | `spec-reportes.md` (pendiente) | Reportes por texto o voz, PDF y Excel, reportes programados | Baja | CU-18, CU-25 | RF-24, RF-25, RF-34 |

- La prioridad de los casos de uso sale de la sección 3.6.3 del documento de requisitos. Las specs de soporte van primero porque las demás las usan.

## Mapa de colecciones y artefactos

| Ubicación | Nombre | Archivo |
|---|---|---|
| — | — | Se completa con `spec-trabajos.md` y las siguientes |

## Mapa de endpoints

Prefijo `/api/ia/v1`. Se completa con cada spec.

| Ruta | Métodos | Archivo |
|---|---|---|
| — | — | — |

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
| D-07 | **Roles:** `administrador`, `gerencia` y `tecnico_campo` para usuarios. Los roles de las cuentas de servicio que leen resultados o piden reportes programados (constitución §9) se definen en la spec que los necesita y se agregan al realm (`specs/spec-keycloak-realm.md` lo deja pendiente). La cuenta de servicio propia (`servicio-ia`) ya tiene `lectura_gestion`, `lectura_inventario` y `lectura_operaciones`. |
| D-08 | **Consulta a otros microservicios:** siempre `GET {API_GATEWAY_URL}/api/<servicio>/v1/...` con token de cuenta de servicio (client credentials contra `KEYCLOAK_TOKEN_URL`, en caché hasta 30 s antes de vencer), tiempo límite por llamada (5 s por defecto) y un solo intento. Única excepción: un `401` renueva el token y repite una vez. El cliente solo expone lecturas (RN-14). |
| D-09 | **Correlación:** `X-Correlation-Id` con el mismo formato que el gateway (`[A-Za-z0-9-]{1,64}`); si falta o no coincide, se genera un UUID. Se propaga a las respuestas, a las llamadas al gateway y, desde `spec-trabajos.md`, a los mensajes y trabajos. |
| D-10 | **Logs:** JSON de una línea por registro en la salida estándar, con `fecha`, `nivel`, `logger`, `mensaje`, `idCorrelacion` y campos extra. Un log de acceso por solicitud propio (el de uvicorn se desactiva). Nunca tokens, secretos ni nombres; solo el `sub`. |
| D-11 | **Variables de entorno:** las de `docker-compose.yml`. Se leen con `pydantic-settings` en `app/config.py`; si falta una obligatoria, el proceso no arranca. Cada spec agrega las suyas. |
| D-12 | **Tests:** unitarios sin red ni contenedores (dobles de los `Protocol` de `integracion`, `httpx.MockTransport` para HTTP, tokens firmados con una clave RSA local). Los de integración levantan la aplicación con el `TestClient` de FastAPI; desde `spec-trabajos.md` usan además los emuladores de Firestore y GCS y RabbitMQ de Docker Compose (en GitHub Actions, como contenedores de servicio). |
| D-13 | **Cobertura:** `pytest-cov` sobre `app`, excluyendo `app/integracion` y `app/ml` (constitución §8). Incluye `comun`, `config` y `main` además de los módulos de capacidad: es más estricto que el mínimo de la constitución. Umbral 80 %. |
| D-14 | **OpenAPI:** lo genera FastAPI desde el código (`/openapi.json`, `/docs`). Cada ruta declara sus respuestas de error con `RespuestaError`; un test falla si una ruta del prefijo no documenta las suyas. |

## Catálogo de códigos de error

| HTTP | Código | Archivo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Todos |
| 401 | `NO_AUTENTICADO` | Todos |
| 403 | `SIN_PERMISO` | Todos |
| 404 | `RECURSO_NO_ENCONTRADO` | Todos (ruta inexistente) |
| 405 | `METODO_NO_PERMITIDO` | Todos |
| 500 | `ERROR_INTERNO` | Todos (sin exponer detalles) |
| 503 | `AUTENTICACION_NO_DISPONIBLE` | Todos (no se pueden obtener las claves de Keycloak) |
| 503 | `DEPENDENCIA_NO_DISPONIBLE` | Los que consultan otros microservicios |

Criterio: `400` para formato (lo valida el esquema Pydantic); `422` para reglas propias del servicio (por ejemplo, datos insuficientes para estimar).

## Matriz de trazabilidad

| Requisito | Descripción resumida | Archivos |
|---|---|---|
| RN-14 | Los agentes y el servicio solo consultan | base (cliente de solo lectura) |
| RN-16 | Permisos verificados en el servidor | base, todos |
| RNF-02 | Validación del JWT en cada solicitud | base |
| RNF-03 | Secretos por variables de entorno | base |
| RNF-08 | La caída de otro servicio no tumba este | base |
| RNF-18 | OpenAPI | base, todos |
| RNF-19, RNF-20 | Docker Compose y pipeline propio | base |
| RNF-22 | Correlación | base, trabajos |

Se completa con cada spec.

## Diferencias intencionales con el documento de requisitos

Donde difieren, prevalece la constitución.

| Documento de requisitos | Specs y constitución | Motivo |
|---|---|---|
| No menciona base de datos para el servicio de IA | Firestore (trabajos y resultados) y Cloud Storage (modelos y reportes) | Constitución §2 y §4; ambos en GCP, donde se despliega el servicio |
| RNF-17 asigna arquitectura a tres servicios | Módulos por capacidad | Constitución v3.0.0 §3: el servicio casi no tiene lógica de negocio |

## Historial de decisiones (2026-11-04)

- Arquitectura por módulos de capacidad (constitución v3.0.0).
- La base del servicio va en su propia spec, sin funcionalidad de negocio, porque la usan las cinco siguientes.
- `DEPENDENCIA_NO_DISPONIBLE` en lugar de reutilizar `SERVICIO_NO_DISPONIBLE`, que es el código del gateway cuando este servicio está caído: así el cliente distingue "IA no responde" de "IA no pudo obtener los datos".
