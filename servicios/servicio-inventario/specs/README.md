# Specs — `servicio-inventario`

Un archivo por funcionalidad, cada uno con tres partes: **Spec** (qué hace), **Plan** (cómo se construye) y **Tareas** (en qué orden se implementa).

- Constitución de referencia: `servicio-inventario` v2.8.0 (2026-11-02). Si un archivo la contradice, prevalece la constitución.
- Documento de requisitos: `SW2_Parcial_2.pdf` (CU, RF, RN y RNF).
- Criterio: lo más simple que cumpla el documento de requisitos y la constitución. Es un proyecto de examen, no un sistema en producción.

## Cómo usar estos archivos

Quien implemente (persona o agente) necesita tres cosas en el repositorio: la constitución (`servicios/servicio-inventario/Constitucion.md`), este README y el archivo de la funcionalidad. Las funcionalidades se implementan en el orden del índice; cada una se termina con sus tests en verde antes de pasar a la siguiente.

## Índice y orden de implementación

| Orden | ID | Archivo | Funcionalidad | Prioridad | CU | RF |
|---|---|---|---|---|---|---|
| 1 | 001 | [spec-insumos.md](spec-insumos.md) | Catálogo de insumos + **Fase 0: base del servicio** | Alta | CU-06 | RF-07 |
| 2 | 002 | [spec-movimientos.md](spec-movimientos.md) | Entradas y salidas manuales, stock resultante | Alta | CU-07 | RF-08 |
| 3 | 003 | [spec-estado-inventario.md](spec-estado-inventario.md) | Estado del inventario frente al nivel mínimo | Media | CU-24 | RF-33, RF-27 |
| 4 | 004 | [spec-stock-bajo.md](spec-stock-bajo.md) | Evento `inventario.stock.bajo` con la regla de 24 h | Media | CU-09 | RF-09 |
| 5 | 005 | [spec-descuento-saga.md](spec-descuento-saga.md) | Descuento y restauración de insumos en la Saga | Media (se implementa junto con CU-12) | CU-08 | RF-10 |

- CU, RF y prioridad salen de las secciones 3.6.3 y 3.8 del documento de requisitos.
- El evento de stock bajo va antes de la Saga porque introduce RabbitMQ con un caso más simple (solo publicar).
- La Saga va al final, con movimientos y stock bajo ya probados, y se integra junto con `servicio-operaciones`.

## Mapa de la base de datos

MongoDB, base `inventario_db`. Los índices se crean con migraciones versionadas en `migrations/` (constitución §4); Mongoose no crea índices (`autoIndex: false`).

| Migración | Colección | Archivo |
|---|---|---|
| `001-crear-indices-auditoria.ts` | `registros_auditoria` | spec-insumos.md (Fase 0) |
| `002-crear-indices-insumos.ts` | `insumos` | spec-insumos.md |
| `003-crear-indices-movimientos.ts` | `movimientos_inventario` | spec-movimientos.md |
| — (usa `_id` = `idSaga`) | `sagas_procesadas` | spec-descuento-saga.md |
| — (la crea el ejecutor) | `migraciones` | spec-insumos.md (Fase 0) |

## Mapa de endpoints

Prefijo `/api/inventario/v1`.

| Ruta | Métodos | Archivo |
|---|---|---|
| `/insumos`, `/insumos/{id}` | `POST`, `GET`, `PUT` | spec-insumos.md |
| `/movimientos`, `/movimientos/{id}` | `POST`, `GET` | spec-movimientos.md |
| `/estado-inventario` | `GET` | spec-estado-inventario.md |

Fuera del prefijo, sin token: `/salud`, `/salud/liveness`, `/salud/readiness`, `/api-docs` y `/api-docs-json`.

## Mapa de mensajería

| Recurso | Tipo | Dirección | Archivo |
|---|---|---|---|
| Exchange `eventos` (topic, durable), routing key `inventario.stock.bajo` | Evento `StockBajo` | Salida | spec-stock-bajo.md |
| Cola `servicio-inventario.comandos` | `DescontarInsumos`, `RestaurarInsumos` | Entrada | spec-descuento-saga.md |
| Cola `servicio-inventario.comandos.dlq` | Mensajes fallidos | — | spec-descuento-saga.md |
| Cola `servicio-operaciones.respuestas-saga` | `InsumosDescontados`, `InsumosRechazados`, `InsumosRestaurados` | Salida | spec-descuento-saga.md |

## Decisiones transversales

| ID | Decisión |
|---|---|
| D-01 | **Moneda:** boliviano (`BOB`). `costoUnitario` admite hasta 4 decimales y sale con escala 4 (`"82.0500"`). El costo total de la Saga sale con 2 decimales (`"820.50"`). La API no repite la moneda en cada monto; se documenta en OpenAPI. |
| D-02 | **Cantidades:** `stock`, `nivelMinimo` y `cantidad` admiten hasta 3 decimales y salen siempre con escala 3 (`"120.500"`, también con `UNIDAD`: `"12.000"`). Con la unidad `UNIDAD` solo se aceptan enteros. |
| D-03 | **Redondeo:** solo se redondea el costo total de la Saga (precisión completa y redondeo final a 2 decimales, mitad hacia arriba). Una entrada con más decimales de los admitidos se rechaza con `400`, nunca se redondea en silencio. |
| D-04 | **Paginación:** `pagina` (desde 0) y `tamanio` (por defecto 20, máximo 100). Respuesta con `items`, `pagina`, `tamanio` y `total`. |
| D-05 | **Concurrencia:** el insumo tiene `version`; `PUT /insumos/{id}` la recibe en el cuerpo y la compara en una actualización condicionada. Los movimientos cambian el stock con actualizaciones atómicas que **no** incrementan `version`, para que una labor no invalide la edición de un administrador. Los choques responden `409 CONFLICTO_CONCURRENCIA`. |
| D-06 | **Auditoría:** usuario o servicio, acción, fecha, entidad e ID, en la misma transacción del cambio (constitución §4). Las lecturas no se auditan. |
| D-07 | **Fechas:** ISO 8601 UTC (`2026-11-02T14:00:00Z`). Este servicio no usa fechas sin hora. |
| D-08 | **Textos:** se recortan espacios. El nombre del insumo es único sin distinguir mayúsculas (campo `nombre_normalizado` en minúsculas con índice único). |
| D-09 | **Decimales en JSON:** el servicio recibe y responde solo texto (`"820.50"`); un número JSON en la entrada se rechaza con `400 DATOS_INVALIDOS`, en REST y en mensajes. |
| D-10 | **Roles (realm de Keycloak):** `administrador`, `gerencia` y `tecnico_campo` para usuarios; `lectura_inventario` para las cuentas de servicio de `servicio-ia`, GraphQL y n8n. Quien solo tiene `tecnico_campo` recibe la vista reducida del insumo, sin datos económicos. |
| D-11 | **Colas de la Saga:** `servicio-inventario.comandos` (durable, dead-letter al exchange por defecto con routing key `servicio-inventario.comandos.dlq`), `servicio-inventario.comandos.dlq` (durable) y `servicio-operaciones.respuestas-saga` (durable, sin argumentos, igual que la declara `servicio-gestion`). Acordado en las constituciones v2.6.0 de inventario y operaciones. |
| D-12 | **Reintentos de mensajes:** en el propio proceso, 3 reintentos con espera de 1 s, 2 s y 4 s; agotados, `nack` sin reencolar y el mensaje pasa a la DLQ. Equivale a lo que hace Spring AMQP en `servicio-gestion`. |
| D-13 | **Tecnología de soporte:** Node.js 24 LTS (la imagen `node:24-alpine` de Docker Compose), NestJS 11, Mongoose 8, `decimal.js`, `jose` (validación del JWT), `amqplib` + `amqp-connection-manager`. Logs JSON con el `ConsoleLogger` de NestJS 11 (`json: true`). Tests con Jest, Supertest y `testcontainers` (`GenericContainer`, sin los módulos `@testcontainers/*`: el health check de `@testcontainers/mongodb` fallaba en GitHub Actions), con las mismas imágenes de Docker Compose (`mongo:8.0`, `rabbitmq:4-management-alpine`). Sin `@nestjs/terminus`, `nestjs-pino`, `passport` ni `migrate-mongo`. |
| D-14 | **Variables de entorno:** las de `docker-compose.yml`: `PORT`, `MONGODB_URI`, `RABBITMQ_URL`, `KEYCLOAK_ISSUER`, `KEYCLOAK_JWKS_URI` y `KEYCLOAK_AUDIENCE` (`servicio-inventario`). Se validan al arrancar; si falta una, el proceso no inicia. |
| D-15 | **Nombres en MongoDB:** colecciones y campos en snake_case (`nivel_minimo`, `id_saga`), como las columnas de la convención común. El dominio y el JSON usan camelCase; los mappers traducen. |
| D-16 | **Idempotencia por `idMensaje`:** el servicio solo consume comandos de Saga, y un `idMensaje` repetido pertenece siempre al mismo `idSaga`, que ya devuelve la misma respuesta. Por eso no hay una colección de mensajes procesados. |
| D-17 | **Identificadores:** UUID v4 como texto en `_id`, generados con `crypto.randomUUID()`. |

## Catálogo de códigos de error

| HTTP | Código | Archivo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Todos |
| 401 | `NO_AUTENTICADO` | Todos |
| 403 | `SIN_PERMISO` | Todos |
| 404 | `INSUMO_NO_ENCONTRADO` | insumos, movimientos |
| 404 | `MOVIMIENTO_NO_ENCONTRADO` | movimientos |
| 404 | `RECURSO_NO_ENCONTRADO` | Todos (ruta inexistente) |
| 409 | `NOMBRE_INSUMO_DUPLICADO` | insumos |
| 409 | `CONFLICTO_CONCURRENCIA` | insumos |
| 422 | `CANTIDAD_INVALIDA` | insumos, movimientos |
| 422 | `NIVEL_MINIMO_INVALIDO` | insumos |
| 422 | `COSTO_UNITARIO_INVALIDO` | insumos |
| 422 | `UNIDAD_NO_MODIFICABLE` | insumos |
| 422 | `STOCK_INSUFICIENTE` | movimientos |
| 500 | `ERROR_INTERNO` | Todos (sin exponer detalles) |

Ruta existente con método no soportado: NestJS responde 404, que se traduce a `RECURSO_NO_ENCONTRADO`.

Códigos de rechazo en mensajes de la Saga (no son HTTP), de la constitución §5:

- `InsumosRechazados`: `DATOS_INVALIDOS`, `INSUMO_NO_ENCONTRADO`, `STOCK_INSUFICIENTE`, `SAGA_COMPENSADA`.

Criterio: `400` para formato (lo valida el DTO); `422` para reglas del dominio (las valida la entidad o el objeto de valor).

## Matriz de trazabilidad

| Requisito | Descripción resumida | Archivos |
|---|---|---|
| RF-07 | Registrar insumos con nombre, categoría, unidad, stock y nivel mínimo | insumos |
| RF-08 | Registrar entradas y salidas de inventario | movimientos |
| RF-09 | Emitir un evento de stock bajo cuando un insumo alcance su nivel mínimo | stock bajo |
| RF-10 | Descontar insumos en la Saga y revertir el descuento si la compensación lo requiere | descuento Saga |
| RF-13, RF-29 | Coordinación de la Saga y alerta por correo de n8n (soporte a otros módulos) | descuento Saga, stock bajo |
| RF-27 | Datos consolidados para React mediante GraphQL (soporte) | insumos, estado del inventario |
| RF-33 | Consultar el estado del inventario frente al nivel mínimo | estado del inventario |
| RN-04 | El stock nunca es negativo; un descuento mayor al disponible se rechaza completo | movimientos, descuento Saga |
| RN-05 | Alerta cuando el stock llega al nivel mínimo | stock bajo, estado del inventario |
| RN-08, RN-09 | Compensación e idempotencia de la Saga | descuento Saga |
| RN-14 | Los agentes de IA solo consultan | insumos, estado del inventario |
| RN-15, RN-16 | Roles y validación en el servidor | Todos |
| RNF-05 | Consultas REST en menos de 3 s | Todos |
| RNF-08 | Independencia frente a la caída de otros servicios | stock bajo, descuento Saga |
| RNF-10, RNF-11, RNF-22 | Fallos de la Saga, Dead Letter Queue y trazabilidad | descuento Saga, Fase 0 |

## Diferencias intencionales con el documento de requisitos

Donde difieren, prevalece la constitución.

| Documento de requisitos | Specs y constitución | Motivo |
|---|---|---|
| RF-07 no incluye costo unitario | `costoUnitario` obligatorio (≥ 0, 4 decimales) | Sin él no existe el costo que la Saga registra en `servicio-gestion` (constitución §3) |
| Unidad de medida como texto libre | `KILOGRAMO` / `LITRO` / `UNIDAD` | Lista cerrada para validar decimales (constitución §3) |
| Cantidades como `Float` | `Decimal128` y `decimal.js`; texto en JSON | Constitución §4 y §11: nunca punto flotante |
| Stock como atributo editable | El stock solo cambia por movimientos; el stock inicial es una entrada | Constitución §3: trazabilidad completa del stock |
| RN-15 no menciona lectura del técnico de campo | `tecnico_campo` consulta insumos sin datos económicos | `ConsumoInsumo` de operaciones referencia el insumo (constitución §7) |
| Proceso 3: n8n recibe un webhook | n8n se suscribe al exchange `eventos` | Constitución v2.7.0: no se pierde el evento si n8n está caído |

## Aclaraciones pendientes

- **AP-01** — Resuelta (2026-11-02): CU, RF y prioridades verificados contra las secciones 3.6.3 y 3.8 de `SW2_Parcial_2.pdf`.
- **AP-02** — Resuelta (constitución v2.8.0): el glosario incluye `fechaUltimaAlerta`, `registros_auditoria`, `migraciones` y el tipo de mensaje `StockBajo`.
- **AP-03** — Resuelta (constitución v2.8.0): `administrador` y `gerencia` consultan movimientos; `lectura_inventario` no, porque la constitución lo limita a insumos y estado del inventario y ninguna integración los necesita (`servicio-ia` obtiene el consumo por labor de `servicio-operaciones`).

## Historial de decisiones (2026-11-02)

- Primera versión de las specs, a partir de la constitución v2.7.0 y de las specs ya aprobadas de `servicio-gestion`.
- Formato de las respuestas de la Saga (`InsumosDescontados` con `costoTotal` e `items`; `InsumosRechazados` con `insumosAfectados`; `InsumosRestaurados` con `sinEfecto`), definido en RQ-SAG-09 de `spec-descuento-saga.md` como contrato que adopta `servicio-operaciones`.
- Constitución v2.8.0 (solo inventario): lectura de movimientos para `administrador` y `gerencia`, y glosario ampliado (AP-02, AP-03).
- Alerta de stock bajo con reserva temporal antes de publicar, para cumplir a la vez "un evento cada 24 h" y "la fecha se guarda solo después de publicar" ante movimientos concurrentes.
- Trazabilidad corregida con el PDF: RF-09 es el evento de stock bajo y RF-10 el descuento de la Saga (estaban intercambiados); CU-24 incluye RF-27; CU-08 y CU-09 tienen prioridad media.
- Migraciones con un ejecutor propio de ~50 líneas en lugar de `migrate-mongo`, por la regla de simplicidad.
