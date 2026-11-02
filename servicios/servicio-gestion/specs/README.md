# Specs — `servicio-gestion`

Un archivo por funcionalidad, cada uno con tres partes: **Spec** (qué hace), **Plan** (cómo se construye) y **Tareas** (en qué orden se implementa).

- Constitución de referencia: `servicio-gestion` v2.4.0 (2026-11-01). Si un archivo la contradice, prevalece la constitución.
- Documento de requisitos: `SW2_Parcial_2.pdf` (CU, RF, RN y RNF).
- Criterio: lo más simple que cumpla el documento de requisitos y la constitución. Es un proyecto de examen, no un sistema en producción.

## Cómo usar estos archivos

Quien implemente (persona o agente) necesita tres cosas en el repositorio: la constitución (`servicios/servicio-gestion/Constitucion.md`), este README y el archivo de la funcionalidad. Las funcionalidades se implementan en el orden del índice; cada una se termina con sus tests en verde antes de pasar a la siguiente.

## Índice y orden de implementación

| Orden | ID | Archivo | Funcionalidad | Prioridad | CU | RF |
|---|---|---|---|---|---|---|
| 1 | 001 | [spec-parcelas.md](spec-parcelas.md) | Parcelas + **Fase 0: base del servicio** | Alta | CU-01 | RF-01 |
| 2 | 002 | [spec-cultivos.md](spec-cultivos.md) | Catálogo de cultivos | Alta | CU-02 | RF-02 |
| 3 | 003 | [spec-campanias.md](spec-campanias.md) | Campañas y ciclo de estado | Alta | CU-03 | RF-03 |
| 4 | 004 | [spec-costos-manuales.md](spec-costos-manuales.md) | Costos manuales y listado de costos | Media | CU-04 | RF-04 |
| 5 | 006 | [spec-produccion.md](spec-produccion.md) | Producción de la campaña | Alta | CU-03 | RF-05 |
| 6 | 007 | [spec-indicadores.md](spec-indicadores.md) | Rendimiento y costo por hectárea | Media | CU-05 | RF-06 |
| 7 | 005 | [spec-costo-saga.md](spec-costo-saga.md) | Registro y anulación de costo en la Saga | Alta (parte de CU-12) | CU-04, CU-12 | RF-04, RF-13 |
| 8 | 008 | [spec-consultas-integracion.md](spec-consultas-integracion.md) | Lectura para operaciones, IA y GraphQL | Soporte | CU-10, CU-12, CU-14, CU-17, CU-18 | RF-18, RF-23, RF-27 |

- La prioridad sale de la sección 3.6.3 del documento de requisitos.
- La Saga va después de tener costos, producción e indicadores probados, y se integra junto con `servicio-operaciones`.

## Mapa de la base de datos

| Migración | Tabla | Archivo |
|---|---|---|
| `V1__crear_registro_auditoria.sql` | `registro_auditoria` | spec-parcelas.md (Fase 0) |
| `V2__crear_parcela.sql` | `parcela` | spec-parcelas.md |
| `V3__crear_cultivo.sql` | `cultivo` | spec-cultivos.md |
| `V4__crear_campania.sql` | `campania` | spec-campanias.md |
| `V5__crear_costo_campania.sql` | `costo_campania` | spec-costos-manuales.md |
| `V6__crear_produccion_campania.sql` | `produccion_campania` | spec-produccion.md |
| `V7__crear_tablas_saga.sql` | `saga_procesada`, `mensaje_procesado` | spec-costo-saga.md |

## Mapa de endpoints

Prefijo `/api/gestion/v1`.

| Ruta | Métodos | Archivo |
|---|---|---|
| `/parcelas`, `/parcelas/{id}` | `POST`, `GET`, `PUT` | spec-parcelas.md |
| `/cultivos`, `/cultivos/{id}` | `POST`, `GET`, `PUT` | spec-cultivos.md |
| `/campanias`, `/campanias/{id}` | `POST`, `GET`, `PUT` | spec-campanias.md |
| `/campanias/{id}/estado` | `PUT` (cambiar estado) | spec-campanias.md |
| `/campanias/{id}/estado` | `GET` (consulta de integración) | spec-consultas-integracion.md |
| `/campanias/{id}/costos` | `POST`, `GET` | spec-costos-manuales.md |
| `/campanias/{id}/costos/{idCosto}` | `PUT`, `DELETE` | spec-costos-manuales.md |
| `/campanias/{id}/produccion` | `PUT`, `GET` | spec-produccion.md |
| `/campanias/{id}/indicadores` | `GET` | spec-indicadores.md |
| `/campanias/historicos` | `GET` | spec-consultas-integracion.md |

Fuera del prefijo, sin token: `/salud`, `/salud/liveness`, `/salud/readiness`, `/v3/api-docs` y `/swagger-ui.html`.

## Decisiones transversales

| ID | Decisión |
|---|---|
| D-01 | **Moneda:** boliviano (`BOB`, `Bs`), 2 decimales. La API no repite la moneda en cada monto; se documenta en OpenAPI. |
| D-02 | **Superficie:** hectáreas, hasta 4 decimales. |
| D-03 | **Producción:** kilogramos para todos los cultivos, hasta 2 decimales; rendimiento en kg/ha. El cultivo guarda `unidadMedida` (RF-02), hoy solo `KILOGRAMO`. |
| D-04 | **Redondeo:** cálculos con precisión completa y redondeo final a 2 decimales, mitad hacia arriba. Una entrada con más decimales de los admitidos se rechaza con `400`. |
| D-05 | **Paginación:** `pagina` (desde 0) y `tamanio` (por defecto 20, máximo 100; 500 en históricos). Respuesta con `items`, `pagina`, `tamanio` y `total`. |
| D-06 | **Concurrencia:** `@Version` de JPA. Parcelas, cultivos y campañas reciben la `version` en el cuerpo de `PUT`; costos y producción se protegen con la versión interna de la campaña. Los choques responden `409 CONFLICTO_CONCURRENCIA`. |
| D-07 | **Auditoría:** usuario o servicio, acción, fecha, entidad e ID, en la misma transacción del cambio. Exactamente lo que piden el documento de requisitos (§1.7.3) y la constitución (§4). Las lecturas no se auditan. |
| D-08 | **Fechas:** sin hora como `AAAA-MM-DD`; con hora en ISO 8601 UTC. |
| D-09 | **Textos:** se recortan espacios; las unicidades no distinguen mayúsculas. |
| D-10 | **Decimales en JSON:** el servicio responde y recibe solo texto (`"820.50"`); un número JSON en la entrada se rechaza con `400 DATOS_INVALIDOS`. |
| D-11 | **Roles (realm de Keycloak):** `administrador`, `gerencia`, `tecnico_campo` para usuarios; `lectura_gestion` (`servicio-ia`, GraphQL) y `estado_campania` (`servicio-operaciones`, GraphQL) para cuentas de servicio. |
| D-12 | **Colas de la Saga:** `servicio-gestion.comandos` (entrada), `servicio-gestion.comandos.dlq` (errores) y `servicio-operaciones.respuestas-saga` (respuestas). 3 reintentos con espera creciente y luego DLQ. A acordar con `servicio-operaciones`. |
| D-13 | **Tecnología de soporte:** Spring Boot 3.4 (logs JSON nativos); tests con Testcontainers y `jwt()` de `spring-security-test`, sin Keycloak; sin Lombok ni MapStruct. |
| D-14 | **Variables de entorno:** las de `docker-compose.yml`, incluidos `SPRING_*` y `KEYCLOAK_*`, para evitar traducciones en `application.yml`. Testcontainers usa las mismas versiones de PostgreSQL y RabbitMQ que Docker Compose. |

## Catálogo de códigos de error

| HTTP | Código | Archivo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Todos |
| 401 | `NO_AUTENTICADO` | Todos |
| 403 | `SIN_PERMISO` | Todos |
| 404 | `PARCELA_NO_ENCONTRADA` | parcelas, campañas |
| 404 | `CULTIVO_NO_ENCONTRADO` | cultivos, campañas |
| 404 | `CAMPANIA_NO_ENCONTRADA` | campañas, costos manuales, producción, indicadores, consultas de integración |
| 404 | `COSTO_NO_ENCONTRADO` | costos manuales |
| 404 | `PRODUCCION_NO_REGISTRADA` | producción |
| 404 | `RECURSO_NO_ENCONTRADO` | Todos (ruta inexistente) |
| 405 | `METODO_NO_PERMITIDO` | Todos |
| 409 | `NOMBRE_PARCELA_DUPLICADO` | parcelas |
| 409 | `CULTIVO_DUPLICADO` | cultivos |
| 409 | `CONFLICTO_CONCURRENCIA` | parcelas, cultivos, campañas, costos manuales, producción |
| 409 | `PARCELA_CON_CAMPANIA_EN_CURSO` | campañas |
| 422 | `SUPERFICIE_INVALIDA` | parcelas |
| 422 | `FECHAS_INVALIDAS` | campañas |
| 422 | `TRANSICION_ESTADO_INVALIDA` | campañas |
| 422 | `FINALIZACION_SIN_PRODUCCION` | campañas |
| 422 | `CAMPO_NO_MODIFICABLE` | campañas |
| 422 | `CAMPANIA_FINALIZADA` | campañas, costos manuales, producción |
| 422 | `CAMPANIA_NO_EN_CURSO` | producción |
| 422 | `MONTO_INVALIDO` | costos manuales |
| 422 | `FECHA_COSTO_INVALIDA` | costos manuales |
| 422 | `COSTO_NO_EDITABLE` | costos manuales |
| 422 | `PRODUCCION_INVALIDA` | producción |
| 422 | `FECHA_COSECHA_INVALIDA` | producción |
| 500 | `ERROR_INTERNO` | Todos (sin exponer detalles) |

Códigos de rechazo en mensajes de la Saga (no son HTTP):

- `CostoCampaniaRechazado`: `DATOS_INVALIDOS`, `CAMPANIA_NO_ENCONTRADA`, `CAMPANIA_FINALIZADA`, `SAGA_ANULADA`.
- `AnulacionCostoRechazada`: `DATOS_INVALIDOS`, `CAMPANIA_FINALIZADA`.

Criterio: `400` para formato (lo valida el DTO); `422` para reglas del dominio (las valida el agregado).

## Matriz de trazabilidad

| Requisito | Descripción resumida | Archivos |
|---|---|---|
| RF-01 | Registrar, editar y consultar parcelas | parcelas |
| RF-02 | Registrar cultivos con nombre, variedad y unidad de medida | cultivos |
| RF-03 | Crear campañas con cultivo, parcela, fechas y estado | campañas |
| RF-04 | Registrar costos manuales y desde la Saga | costos manuales, costo Saga |
| RF-05 | Registrar la producción al finalizar la campaña | producción |
| RF-06 | Calcular rendimiento y costo por hectárea | indicadores |
| RF-13, RF-18, RF-23, RF-27 | Saga, datos para IA, agentes y GraphQL (soporte a otros módulos) | costo Saga, consultas de integración |
| RN-01 | Superficie > 0; campaña con cultivo, parcela y fechas coherentes | parcelas, campañas |
| RN-02 | Estados en secuencia, sin retroceso | campañas |
| RN-03 | Indicadores solo con producción y costos | producción, indicadores |
| RN-06 | Labores solo en campañas no finalizadas | campañas, costo Saga, consultas de integración |
| RN-08, RN-09 | Compensación e idempotencia de la Saga | costo Saga |
| RN-14 | Los agentes solo consultan | consultas de integración |
| RN-15, RN-16 | Roles y validación en el servidor | Todos |
| RNF-05 | Consultas REST en menos de 3 s | Todos |
| RNF-08, RNF-09 | Independencia y operaciones offline sin pérdida | consultas de integración |
| RNF-10, RNF-11, RNF-22 | Fallos de la Saga, Dead Letter Queue y trazabilidad | costo Saga, Fase 0 |

## Diferencias intencionales con el documento de requisitos

Donde difieren, prevalece la constitución.

| Documento de requisitos | Specs y constitución | Motivo |
|---|---|---|
| `monto`, `superficie`, `produccionObtenida` como `Float` | `BigDecimal` / `NUMERIC`; texto en JSON | Constitución §4 y §11: nunca punto flotante |
| `CategoriaCosto.MANO_OBRA` | `MANO_DE_OBRA` | Glosario de la constitución |
| `produccionObtenida` como atributo de `Campaña` | `ProduccionCampania` dentro del agregado, con fecha de cosecha | Permite corregirla antes de finalizar |
| `Campaña` sin nombre | `nombre` como etiqueta del periodo productivo | El documento menciona el "periodo productivo" (§1.7.3) |
| `Cultivo.unidadMedida` como texto libre | Único valor `KILOGRAMO` | D-03: rendimiento comparable en kg/ha |
| RN-15 no menciona lectura del técnico de campo | `tecnico_campo` consulta parcelas y campañas no finalizadas | Necesario para registrar labores (CU-10, RN-06) |

## Historial de decisiones (2026-11-01)

- Moneda `BOB`, producción en kg y producción obligatoria para finalizar, registrada en `EN_CURSO`.
- La campaña copia la superficie de la parcela; máximo una campaña `EN_CURSO` por parcela.
- Compensación `AnularCostoCampania` y rechazo `SAGA_ANULADA` (constituciones v2.1.0 de gestión y operaciones).
- Costos manuales de `INSUMO` permitidos; los costos manuales se eliminan físicamente.
- Sin indicadores por lote ni permisos para n8n.
- Simplificación para el examen: auditoría con usuario, acción, fecha y entidad (sin valor anterior y nuevo); dos roles de servicio (`lectura_gestion` y `estado_campania`); un archivo por funcionalidad.
- Trazabilidad completada con `SW2_Parcial_2.pdf`; se agregó la unidad de medida del cultivo por RF-02 (constitución de gestión v2.2.0).
- Un solo repositorio: el pipeline de este servicio está en `.github/workflows/servicio-gestion.yml`, en la raíz (constitución v2.3.0).
- Decimales de entrada solo como texto (D-10), para cumplir la convención común de la constitución.
- Validación del token con `jwk-set-uri` e `issuer-uri`, porque el emisor (`localhost:8180`) no es alcanzable desde el contenedor.
- Ante tiempo límite, la anulación del costo va antes que la restauración de insumos (constitución de operaciones v2.4.0).
- Revisión de specs: errores 403, 404 y 405 explícitos; audiencia con la propiedad `audiences`; fechas estrictas en Jackson; indicadores calculados con valores, también en históricos; `motivosNoDisponible` en históricos; listado de campañas sin `resumen`.
- Regla de una campaña `EN_CURSO` por parcela en el caso de uso y en el índice único (constitución de gestión v2.4.0).
