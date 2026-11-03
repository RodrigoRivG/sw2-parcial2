# Specs — `servicio-operaciones`

Un archivo por funcionalidad, cada uno con tres partes: **Spec** (qué hace), **Plan** (cómo se construye) y **Tareas** (en qué orden se implementa).

- Constitución de referencia: `servicio-operaciones` v2.8.0 (2026-11-02). Si un archivo la contradice, prevalece la constitución.
- Documento de requisitos: `SW2_Parcial_2.pdf` (CU, RF, RN y RNF).
- Contratos ya implementados que este servicio consume: `servicio-inventario/specs/spec-descuento-saga.md` (RQ-SAG-09 y colas de 2.1), `servicio-gestion/specs/spec-costo-saga.md` (2.2 y 2.3) y `servicio-gestion/specs/spec-consultas-integracion.md` (`GET /campanias/{id}/estado`).
- Criterio: lo más simple que cumpla el documento de requisitos y la constitución. Es un proyecto de examen, no un sistema en producción.

## Cómo usar estos archivos

Quien implemente (persona o agente) necesita tres cosas en el repositorio: la constitución (`servicios/servicio-operaciones/Constitucion.md`), este README y el archivo de la funcionalidad. Las funcionalidades se implementan en el orden del índice; cada una se termina con sus tests en verde antes de pasar a la siguiente.

## Índice y orden de implementación

| Orden | ID | Archivo | Funcionalidad | Prioridad | CU | RF |
|---|---|---|---|---|---|---|
| 1 | 001 | [spec-labores.md](spec-labores.md) | Programar y registrar labores, validación de campaña, idempotencia + **Fase 0: base del servicio** | Alta | CU-10 | RF-11, RF-14, RF-30 |
| 2 | 002 | [spec-saga.md](spec-saga.md) | Coordinación de la Saga, compensaciones y recuperación | Alta | CU-12 | RF-13 |
| 3 | 003 | [spec-revision-labores.md](spec-revision-labores.md) | Resolución de labores `PENDIENTE_REVISION` | Alta (parte de CU-12) | CU-12 | RF-13 |
| 4 | 004 | [spec-incidencias.md](spec-incidencias.md) | Incidencias con fotografía, clasificación de IA y evento | Media | CU-11 | RF-12, RF-31 |
| 5 | 005 | [spec-sincronizacion.md](spec-sincronizacion.md) | Sincronización de operaciones offline por lotes | Media | CU-13 | RF-14 a RF-17 |

- CU, RF y prioridad salen de las secciones 3.1.1, 3.6.3 y 3.8 del documento de requisitos.
- La Saga va segunda porque los dos participantes ya están implementados y probados. Mientras no exista, una labor realizada con insumos queda `PENDIENTE` sin Saga (`spec-labores.md`, RQ-LAB-08).
- La sincronización va al final porque solo reutiliza los casos de uso de labores e incidencias.

## Mapa de la base de datos

Amazon DynamoDB. Las tablas e índices se definen en `database/dynamodb/tablas.json` y se crean con el comando idempotente `php artisan dynamodb:crear-tablas` (constitución §4). Todas usan `PAY_PER_REQUEST` y proyección `ALL` en sus índices.

| Tabla | Clave | Índices secundarios globales | Archivo |
|---|---|---|---|
| `registros_auditoria` | `id` | `gsi_entidad` (`entidad_id`, `fecha`) | spec-labores.md (Fase 0) |
| `labores` | `id` | `gsi_estado`, `gsi_campania`, `gsi_responsable` (por `fecha_referencia`), `gsi_validacion_pendiente` (disperso) | spec-labores.md |
| `sagas` | `id_saga` | `gsi_activas` (disperso, por `fecha_limite`) | spec-saga.md |
| `incidencias` | `id` | `gsi_parcela`, `gsi_campania`, `gsi_registrador` (por `fecha_observacion`), `gsi_notificacion_pendiente` (disperso) | spec-incidencias.md |

S3: bucket privado `AWS_BUCKET` (`evidencias` en local), prefijo `incidencias/` (spec-incidencias.md).

## Mapa de endpoints

Prefijo `/api/operaciones/v1`.

| Ruta | Métodos | Archivo |
|---|---|---|
| `/labores`, `/labores/{id}` | `POST`, `GET` | spec-labores.md |
| `/labores/{id}/realizacion` | `POST` | spec-labores.md |
| `/sagas/{id}` | `GET` | spec-saga.md |
| `/labores/{id}/resolucion` | `POST` | spec-revision-labores.md |
| `/incidencias`, `/incidencias/{id}` | `POST`, `GET` | spec-incidencias.md |
| `/sincronizacion` | `POST` | spec-sincronizacion.md |

Fuera del prefijo, sin token: `/salud`, `/salud/liveness`, `/salud/readiness` y `/api-docs` (contrato OpenAPI).

## Mapa de mensajería

| Recurso | Tipo | Dirección | Archivo |
|---|---|---|---|
| Cola `servicio-inventario.comandos` | `DescontarInsumos`, `RestaurarInsumos` | Salida | spec-saga.md |
| Cola `servicio-gestion.comandos` | `RegistrarCostoCampania`, `AnularCostoCampania` | Salida | spec-saga.md |
| Cola `servicio-operaciones.respuestas-saga` | Las siete respuestas de los participantes | Entrada | spec-saga.md |
| Cola `servicio-operaciones.respuestas-saga.dlq` | Respuestas que no se pudieron procesar | — | spec-saga.md |
| Exchange `eventos` (topic, durable), routing key `operaciones.incidencia.registrada` | Evento `IncidenciaRegistrada` | Salida | spec-incidencias.md |

## Procesos

| Proceso | Comando | Desde |
|---|---|---|
| API HTTP | `php artisan serve` (local) / Apache (imagen) | spec-labores.md (Fase 0) |
| Tareas programadas | `php artisan schedule:work` | spec-labores.md (revalidación de campaña) |
| Consumidor de respuestas de la Saga | `php artisan operaciones:consumir-respuestas` | spec-saga.md |

Los tres usan la misma imagen; en Docker Compose son tres servicios (`servicio-operaciones`, `servicio-operaciones-programador` y `servicio-operaciones-consumidor`).

## Decisiones transversales

| ID | Decisión |
|---|---|
| D-01 | **Cantidades:** texto decimal > 0 con hasta 3 decimales (`"2.5"`), las mismas reglas que acepta `servicio-inventario`. Este servicio no conoce la unidad del insumo: si una cantidad decimal no corresponde (unidad `UNIDAD`), la rechaza inventario en la Saga. Se guardan y responden normalizadas con escala 3 (`"2.500"`). |
| D-02 | **Montos:** el costo total de la Saga se recibe de inventario con 2 decimales y se reenvía tal cual a gestión. Este servicio no calcula montos. Moneda `BOB`. |
| D-03 | **Decimales en JSON:** solo texto, en REST y en mensajes; un número JSON en la entrada se rechaza con `400 DATOS_INVALIDOS`. Se comparan con `bcmath`, nunca con `float`. En DynamoDB se guardan como `S` para que el SDK de PHP no los convierta a `float`. |
| D-04 | **Fechas:** con hora en ISO 8601 UTC (`2026-11-02T14:00:00Z`); sin hora como `AAAA-MM-DD` (`fechaProgramada`). Se guardan como texto ISO, que ordena bien en los índices. "Hoy" es la fecha UTC. Tolerancia de reloj del dispositivo: 5 minutos hacia el futuro. |
| D-05 | **Paginación por cursor:** DynamoDB no cuenta ni salta páginas sin leerlas todas, así que los listados usan `limite` (por defecto 20, máximo 100) y `cursor` (opaco, el `LastEvaluatedKey` en base64url). Respuesta `{ items, siguienteCursor }`; `siguienteCursor = null` en la última página. Con filtros secundarios una página puede traer menos de `limite` elementos. Es una diferencia intencional con `pagina`/`total` de los otros servicios. |
| D-06 | **Idempotencia:** el `id` del recurso creado es el `idOperacion` generado en el dispositivo. La creación es un `PutItem` condicional (`attribute_not_exists(id)`) dentro de una transacción con la auditoría. Cada recurso guarda la `huella` (SHA-256 del contenido normalizado más el `sub` del usuario). Repetición con la misma huella → `200` con el estado actual del recurso, sin reprocesar; con otra huella → `409 CONFLICTO_IDEMPOTENCIA`. No hay tabla aparte de idempotencia. |
| D-07 | **Concurrencia:** cada ítem tiene `version`; toda actualización es condicional sobre `version` y, en las transiciones de estado, sobre el estado esperado. Un choque en una solicitud REST responde `409 CONFLICTO_CONCURRENCIA`; en la Saga se relee y se vuelve a aplicar. |
| D-08 | **Atomicidad:** los cambios de una operación (labor, Saga, incidencia y auditoría) se escriben con un solo `TransactWriteItems`. Los mensajes se publican después de esa escritura (constitución §6: el estado se persiste antes de enviar). |
| D-09 | **Auditoría:** tabla `registros_auditoria` con `actor` (`sub` o `servicio-operaciones`), `accion`, `entidad`, `id_entidad`, `id_correlacion` y `fecha`, en la misma transacción del cambio. Las lecturas no se auditan. |
| D-10 | **Roles (realm de Keycloak):** `administrador`, `gerencia` y `tecnico_campo` para usuarios; `lectura_operaciones` para las cuentas de servicio de n8n, `servicio-ia` y GraphQL (lectura de labores, incidencias y Sagas). La cuenta de servicio de este servicio (`KEYCLOAK_CLIENT_ID = servicio-operaciones`) tiene en el realm el rol `estado_campania` de `servicio-gestion` y un Audience mapper que agrega `servicio-gestion` a `aud`; sin él, gestión rechaza el token con `401` (valida su propia audiencia). |
| D-11 | **Responsable:** se toma del token: `sub` y una copia de `name` (o `preferred_username` si falta). Nunca del cuerpo de la solicitud (constitución §3). |
| D-12 | **Consulta de campaña:** `GET {API_GATEWAY_URL}/api/gestion/v1/campanias/{id}/estado` con token de cuenta de servicio (client credentials contra `KEYCLOAK_TOKEN_URL`, en caché hasta 30 s antes de vencer), tiempo límite de 2 s y un solo intento por solicitud. Es la única llamada síncrona (constitución §7). |
| D-13 | **Colas de la Saga:** se declaran con los mismos argumentos que los participantes: `servicio-inventario.comandos` y `servicio-gestion.comandos` durables con `x-dead-letter-exchange: ""` y `x-dead-letter-routing-key: <cola>.dlq`; `servicio-operaciones.respuestas-saga` durable y **sin argumentos** (así la declaran inventario y gestión; un argumento distinto haría fallar la declaración). Por eso la DLQ de respuestas se alimenta publicando el mensaje en `servicio-operaciones.respuestas-saga.dlq` antes de confirmarlo, como hace gestión con los sobres no interpretables. |
| D-14 | **Reintentos de mensajes consumidos:** en el propio proceso, 3 reintentos con espera de 1 s, 2 s y 4 s; agotados, el mensaje va a la DLQ. Igual que en inventario (D-12) y gestión. |
| D-15 | **Tecnología de soporte:** PHP 8.4 (imagen `sw2/laravel-dev`), Laravel en su última versión estable al crear el proyecto (fijada en `composer.json`), `aws/aws-sdk-php` (DynamoDB y S3), `php-amqplib/php-amqplib`, `firebase/php-jwt` (validación del JWT con JWKS), Pest con `pcov` para la cobertura. Logs JSON con el `JsonFormatter` de Monolog. Sin Eloquent, Sanctum, Passport, Horizon ni paquetes de OpenAPI: el contrato es un `openapi.yaml` escrito a mano. |
| D-16 | **Variables de entorno:** las de `docker-compose.yml` (`DYNAMODB_ENDPOINT`, `AWS_*`, `AWS_ENDPOINT`, `AWS_USE_PATH_STYLE_ENDPOINT`, `AWS_BUCKET`, `RABBITMQ_*`, `API_GATEWAY_URL`, `KEYCLOAK_*`) más `AWS_ENDPOINT_PUBLICO` (endpoint con el que se firman las URL de las fotos: `http://localhost:4566` en local, vacío en la nube), `RABBITMQ_VHOST` (por defecto `/`), `RABBITMQ_SSL` (`true` en la nube) y `DYNAMODB_PREFIJO_TABLAS` (vacío salvo en tests). Se validan al arrancar; si falta una obligatoria, el proceso no inicia. |
| D-17 | **Infraestructura de tests:** los tests usan DynamoDB Local, RabbitMQ y LocalStack reales: en local, los de Docker Compose (con `scripts/ejecutar.sh` y `docker compose --profile operaciones up -d localstack`); en GitHub Actions, contenedores de servicio con las mismas imágenes. Se aíslan con el prefijo de tablas `pruebas_<aleatorio>_`, el vhost de RabbitMQ `pruebas` y el bucket `evidencias-pruebas`, que crea `tests/bootstrap.php` (declarado como `bootstrap` en `phpunit.xml`, con borrado de las tablas al terminar). Así no chocan con los consumidores de inventario y gestión que estén corriendo. Las pruebas de concurrencia usan `EnParalelo` (`tests/Support`), que lanza procesos con `pcntl_fork` (la extensión ya está en la imagen); cada proceso hijo arranca su propia aplicación y sus clientes, porque las conexiones no se comparten entre procesos. |
| D-18 | **Identificadores:** UUID v4 en minúsculas. Los de operaciones los genera el dispositivo; `idSaga`, `idMensaje` y los de auditoría, el servidor. |
| D-19 | **Textos:** se recortan espacios. `observaciones` y `descripcion` admiten hasta 500 y 1000 caracteres. |

## Catálogo de códigos de error

| HTTP | Código | Archivo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Todos |
| 401 | `NO_AUTENTICADO` | Todos |
| 403 | `SIN_PERMISO` | Todos |
| 404 | `LABOR_NO_ENCONTRADA` | labores, revisión, sincronización |
| 404 | `CAMPANIA_NO_ENCONTRADA` | labores |
| 404 | `SAGA_NO_ENCONTRADA` | saga |
| 404 | `INCIDENCIA_NO_ENCONTRADA` | incidencias |
| 404 | `RECURSO_NO_ENCONTRADO` | Todos (ruta inexistente) |
| 405 | `METODO_NO_PERMITIDO` | Todos |
| 409 | `CONFLICTO_IDEMPOTENCIA` | labores, incidencias, sincronización |
| 409 | `CONFLICTO_CONCURRENCIA` | labores, revisión |
| 409 | `SAGA_EN_CURSO` | revisión |
| 422 | `CAMPANIA_FINALIZADA` | labores, revisión |
| 422 | `PARCELA_NO_CORRESPONDE` | labores |
| 422 | `CANTIDAD_INVALIDA` | labores |
| 422 | `FECHA_PROGRAMADA_INVALIDA` | labores |
| 422 | `FECHA_EJECUCION_INVALIDA` | labores |
| 422 | `LABOR_NO_PROGRAMADA` | labores |
| 422 | `LABOR_NO_EN_REVISION` | revisión |
| 422 | `DECISION_NO_PERMITIDA` | revisión |
| 422 | `FOTO_INVALIDA` | incidencias |
| 422 | `FECHA_OBSERVACION_INVALIDA` | incidencias |
| 422 | `CONFIANZA_INVALIDA` | incidencias |
| 500 | `ERROR_INTERNO` | Todos (sin exponer detalles) |

Criterio: `400` para formato (lo valida el `FormRequest`); `422` para reglas del dominio (las valida la entidad o el caso de uso).

Motivos que quedan en la labor (`motivo.codigo`), visibles para el usuario (RNF-14):

- Labor `RECHAZADA`: `CAMPANIA_FINALIZADA`, `CAMPANIA_NO_ENCONTRADA` o `PARCELA_NO_CORRESPONDE` (tras una validación diferida); `STOCK_INSUFICIENTE`, `INSUMO_NO_ENCONTRADO` o `DATOS_INVALIDOS` (de inventario); `RECHAZADA_EN_REVISION` (resolución del administrador).
- Labor `PENDIENTE_REVISION`: `COSTO_RECHAZADO`, `SIN_RESPUESTA_INVENTARIO`, `SIN_RESPUESTA_GESTION` y `ANULACION_COSTO_RECHAZADA`.

## Matriz de trazabilidad

| Requisito | Descripción resumida | Archivos |
|---|---|---|
| RF-11 | Programar y registrar labores con tipo, parcela, campaña, fechas, responsable e insumos | labores |
| RF-12 | Registrar incidencias con tipo, descripción, fecha, parcela y fotografía | incidencias |
| RF-13 | Coordinar la Saga y ejecutar compensaciones | saga, revisión |
| RF-14 | Recibir operaciones offline con idempotencia por UUID y escrituras condicionales | labores, incidencias, sincronización |
| RF-15, RF-16 | Operaciones creadas sin conexión con UUID, sincronizadas en orden cronológico | sincronización (lado servidor) |
| RF-17 | Estado de sincronización de cada operación | sincronización |
| RF-20, RF-21 | Guardar el resultado de la clasificación de la fotografía (soporte) | incidencias |
| RF-23, RF-27 | Lectura para agentes de IA y GraphQL (soporte) | labores, saga, incidencias |
| RF-30 | Recordatorios de labores programadas de n8n (soporte) | labores |
| RF-31 | Notificación de incidencias de n8n (soporte) | incidencias |
| RN-06 | Labor con parcela y campaña; no en campañas finalizadas | labores |
| RN-07 | Programada sin efectos; realizada sin insumos directa; con insumos activa la Saga | labores, saga |
| RN-08 | Rechazo por stock; compensación y revisión ante fallo de costo | saga, revisión |
| RN-09 | Compensaciones idempotentes | saga |
| RN-10 | UUID por operación; lo ya procesado devuelve el resultado anterior | labores, incidencias, sincronización |
| RN-11 | Orden cronológico; las rechazadas no se borran | sincronización, labores |
| RN-12 | Sesión válida para sincronizar (el servidor exige el JWT) | sincronización |
| RN-13 | Resultados de IA orientativos | incidencias |
| RN-15, RN-16 | Roles y validación en el servidor | Todos |
| RNF-05 | Consultas REST en menos de 3 s | Todos |
| RNF-08 | Independencia frente a la caída de otros servicios | labores, saga, incidencias |
| RNF-09 | Operaciones offline sin pérdida | labores, sincronización |
| RNF-10, RNF-11 | Fallos de la Saga, recuperación del coordinador y Dead Letter Queue | saga |
| RNF-14 | Estado y motivo de error por operación | sincronización, labores |
| RNF-22 | Correlación en mensajes y estado de la Saga por paso | saga, Fase 0 |

## Diferencias intencionales con el documento de requisitos

Donde difieren, prevalece la constitución.

| Documento de requisitos | Specs y constitución | Motivo |
|---|---|---|
| `tipoLabor : String` | Enumeración `TipoLabor` | Lista cerrada para que n8n, IA y GraphQL agrupen sin texto libre (AP-01) |
| `responsable : String` | `sub` de Keycloak más copia del nombre | Constitución §3: no es texto libre |
| `ConsumoInsumo.cantidad : Float`, `confianzaIA : Float` | Texto decimal en JSON | Convención común de la constitución: nunca punto flotante |
| `fotoUrl : String` | Clave del objeto S3 y URL prefirmada de corta duración | Constitución §4: bucket privado, nunca URL pública |
| `categoriaIA`, `confianzaIA` | Objeto `clasificacion` con versión del modelo y origen | `servicio-ia` exige guardar la versión que produjo cada resultado (su constitución §4) |
| `TipoIncidencia.DAÑO` | `DANIO` | Convención común: sin ñ |
| Proceso 4: ante fallo de costo se compensan los insumos | Con tiempo límite, primero `AnularCostoCampania` y después `RestaurarInsumos`; con costo `0.00` no se registra costo | Constitución v2.4.0 y v2.5.0 |
| Proceso 3 (y RF-31): n8n recibe un webhook | Evento en el exchange `eventos` | Constitución v2.7.0 |
| Paginación con página y total (resto del sistema) | Cursor | D-05: DynamoDB no cuenta sin leer todo |

## Aclaraciones pendientes

- **AP-01** — Resuelta (constitución v2.8.0): el glosario incluye `TipoLabor`, `ValidacionCampania`, `EstadoSaga`, `PasoSaga`, `EstadoPaso`, `DecisionRevision`, `OrigenClasificacion`, `registros_auditoria`, las rutas de realización y resolución, los mensajes de la Saga, la DLQ de respuestas y el evento `IncidenciaRegistrada`.
- **AP-02** — Resuelta (constitución v2.8.0): lectura para integración con el rol `lectura_operaciones`; "registrar labores" incluye la realización de una programada; la resolución incluye `REINTENTAR`.
- **AP-03** — Resuelta (2026-11-02): las incidencias **no** validan la campaña contra `servicio-gestion`. La campaña es opcional e informativa (relación `0..*` "puede asociar" del modelo del documento), no tiene efectos de negocio como la labor y validar obligaría a una validación diferida más. La fotografía es obligatoria (RF-12 la lista entre los datos de la incidencia y la constitución §1 dice "incidencias con fotografía"), de hasta 10 MB.
- **AP-04** — Informativa: `api-gateway` todavía no tiene código. Hasta que exista, en Docker Compose la consulta de campaña falla y las labores quedan `PENDIENTE` con validación diferida (es el comportamiento especificado ante la caída de gestión). Los tests simulan la respuesta de gestión.
- **AP-05** — Resuelta (2026-11-03): T10 de `spec-saga.md` verificó los contratos con inventario y gestión reales y cerró el T09 de `servicio-inventario/specs/spec-descuento-saga.md`.

## Historial de decisiones (2026-11-02)

- Primera versión de las specs, a partir de la constitución v2.7.0 y de las specs ya implementadas de `servicio-gestion` y `servicio-inventario`, cuyos contratos de mensajes y de consulta de campaña se adoptan sin cambios.
- Sin tabla de idempotencia: el `idOperacion` es el `id` del recurso y la escritura condicional se hace sobre la propia tabla (D-06).
- Las validaciones que fallan en el momento (400, 404, 422) no se guardan: un reintento con el mismo `idOperacion` vuelve a validar y, como el estado de una campaña no retrocede, obtiene el mismo resultado. Solo se guarda lo aceptado, incluida la labor con validación diferida.
- Fotos de incidencias en la misma solicitud (`multipart/form-data`), también en el lote de sincronización, para no tener fotos huérfanas ni un segundo paso de subida.
- Constitución v2.8.0 (solo operaciones): glosario y permisos ampliados (AP-01, AP-02). Incidencias sin validación de campaña y con foto obligatoria (AP-03).
- `EnParalelo` (tests): el proceso padre recolecta su basura antes de crear los hijos y los hijos no recolectan lo heredado. Un hijo destruía la copia heredada de una conexión a RabbitMQ y la cerraba por el socket compartido; después el padre esperaba unos 30 s respuestas que nunca llegaban, y algunos tests tardaban 30 s o perdían el heartbeat según el orden de ejecución. La suite completa bajó de 132 s a 41 s. Detectado al implementar `spec-sincronizacion.md`.
- Revisión: en Docker Compose, el programador y el consumidor esperan a que `servicio-operaciones` esté sano antes de arrancar, para no ejecutar `composer install` tres veces sobre el mismo volumen; el token hacia gestión necesita su audiencia (D-10); las pruebas de concurrencia usan procesos reales (D-17), porque los tests HTTP de Laravel corren en un solo proceso.
