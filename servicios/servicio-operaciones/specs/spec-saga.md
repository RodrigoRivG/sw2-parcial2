# Coordinación de la Saga — `servicio-operaciones`

| Campo | Valor |
|---|---|
| Servicio | `servicio-operaciones` |
| Archivo | `specs/spec-saga.md` |
| Estado | Spec aprobada (2026-11-03) · Implementada (2026-11-03) |
| Constitución | v2.8.0 (secciones 4, 6, 8, 10 y 11) |
| Trazabilidad | CU-12 (prioridad alta; incluye CU-08 de inventario y CU-04 de gestión como participantes) · RF-13 · RN-07, RN-08, RN-09 · RNF-08, RNF-10, RNF-11, RNF-22 |
| Depende de | `spec-labores.md` (labor `PENDIENTE` con insumos). Contratos: `servicio-inventario/specs/spec-descuento-saga.md` (RQ-SAG-09, 2.1) y `servicio-gestion/specs/spec-costo-saga.md` (2.2, 2.3) |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Contexto

Cuando una labor realizada con insumos queda `PENDIENTE` (`spec-labores.md`, RQ-LAB-06), este servicio, **único coordinador**, ejecuta la Saga por RabbitMQ: primero inventario descuenta los insumos y calcula su costo; después gestión registra ese costo en la campaña. Si algo falla, envía las compensaciones de lo que pudo aplicarse, en orden inverso y una a la vez (constitución §6).

```text
                     ┌────────────── InsumosRechazados ──────────────▶ labor RECHAZADA
DescontarInsumos ────┤
                     └─ InsumosDescontados ─┬─ costoTotal "0.00" ─────▶ labor CONFIRMADA
                                            └─ RegistrarCostoCampania ─┬─ CostoCampaniaRegistrado ─▶ CONFIRMADA
                                                                       ├─ CostoCampaniaRechazado ──▶ RestaurarInsumos, PENDIENTE_REVISION
                                                                       └─ sin respuesta ──▶ AnularCostoCampania, PENDIENTE_REVISION
                                                                             ├─ CostoCampaniaAnulado ───▶ RestaurarInsumos
                                                                             └─ AnulacionCostoRechazada ─▶ sin restaurar (lo resuelve el administrador)
```

Los participantes ya están implementados y son idempotentes por `idSaga`: se les puede reenviar el mismo comando sin efectos duplicados (RN-09).

## Escenarios de usuario y pruebas

### Historia 1 — Confirmar una labor con insumos (Prioridad: P1)

Como técnico de campo, quiero que mi labor con insumos quede confirmada con el inventario descontado y el costo en la campaña, sin pasos manuales (RF-13).

**Por qué esta prioridad:** es el flujo normal de toda labor con insumos (CU-12).

**Prueba independiente:** con RabbitMQ real y los participantes simulados por el test (leen los comandos y publican respuestas), se registra la labor y se sigue la Saga hasta el final.

**Escenarios de aceptación:**

1. **Dado** que se registra la labor L1 con insumos en la campaña C1, **entonces** se crea la Saga S1 (`EN_CURSO`, paso `DESCONTAR_INSUMOS` `ENVIADO`, 1 intento), L1 guarda `idSaga = S1`, y **después** de guardar ambas se publica `DescontarInsumos` en `servicio-inventario.comandos` con `idCorrelacion = S1`, `origen = servicio-operaciones` y `datos` `{ idSaga: S1, idLabor: L1, items }`.
2. **Dado** que llega `InsumosDescontados` con `costoTotal` `"580.50"`, **entonces** S1 guarda el costo, el paso `DESCONTAR_INSUMOS` queda `COMPLETADO`, `REGISTRAR_COSTO` `ENVIADO`, y se publica `RegistrarCostoCampania` en `servicio-gestion.comandos` con `{ idSaga: S1, idLabor: L1, idCampania: C1, monto: "580.50", categoria: "INSUMO" }`.
3. **Dado** que llega `CostoCampaniaRegistrado`, **entonces** S1 queda `COMPLETADA` y L1 `CONFIRMADA`, en la misma escritura, con auditoría.
4. **Dado** que `InsumosDescontados` trae `costoTotal` `"0.00"`, **entonces** no se envía nada a gestión, `REGISTRAR_COSTO` queda `OMITIDO`, S1 `COMPLETADA` y L1 `CONFIRMADA` (constitución v2.5.0).
5. **Dado** que una labor con validación diferida pasa a válida (`spec-labores.md`, RQ-LAB-10), **entonces** la Saga se inicia igual que en el escenario 1.

---

### Historia 2 — Rechazar la labor si no hay stock (Prioridad: P1)

Como técnico de campo, quiero saber que mi labor se rechazó y por qué, para corregirla (RN-08, RNF-14).

**Prueba independiente:** el inventario simulado responde `InsumosRechazados`.

**Escenarios de aceptación:**

1. **Dado** que llega `InsumosRechazados` con `codigo = STOCK_INSUFICIENTE` e `insumosAfectados`, **entonces** S1 queda `RECHAZADA`, L1 `RECHAZADA` con `motivo` `{ codigo: STOCK_INSUFICIENTE, mensaje: <motivo de inventario>, detalles: <insumosAfectados> }`, y no se envía nada más.
2. **Dado** `INSUMO_NO_ENCONTRADO` o `DATOS_INVALIDOS`, **entonces** igual que el escenario 1, con ese código.

---

### Historia 3 — Compensar cuando gestión rechaza o no responde (Prioridad: P1)

Como administrador, quiero que una labor cuyo costo no pudo registrarse no deje stock descontado sin costo, y que quede marcada para revisión (RN-08).

**Por qué esta prioridad:** son los tests obligatorios de compensación de la constitución §8.

**Prueba independiente:** con reloj fijo, se simula cada respuesta (o su ausencia) de gestión y se verifican los comandos enviados y los estados.

**Escenarios de aceptación:**

1. **Dado** que llega `CostoCampaniaRechazado` (por ejemplo, `CAMPANIA_FINALIZADA`), **entonces** L1 pasa a `PENDIENTE_REVISION` con `motivo.codigo = COSTO_RECHAZADO` (y el código de gestión en `detalles`), S1 a `COMPENSANDO`, `RESTAURAR_INSUMOS` `ENVIADO`, y se publica `RestaurarInsumos` `{ idSaga: S1, idLabor: L1 }`.
2. **Dado** que después llega `InsumosRestaurados`, **entonces** S1 queda `COMPENSADA` y L1 sigue `PENDIENTE_REVISION`.
3. **Dado** que `RegistrarCostoCampania` no tiene respuesta, **cuando** vence el tiempo límite, **entonces** se reenvía el mismo comando (mismo `idSaga`, nuevo `idMensaje`) hasta completar 4 envíos.
4. **Dado** que se agotaron los 4 envíos, **entonces** `REGISTRAR_COSTO` queda `SIN_RESPUESTA`, L1 `PENDIENTE_REVISION` con `motivo.codigo = SIN_RESPUESTA_GESTION`, S1 `COMPENSANDO`, `ANULAR_COSTO` `ENVIADO`, y se publica `AnularCostoCampania` `{ idSaga, idLabor, idCampania }`. **No** se envía `RestaurarInsumos` todavía.
5. **Dado** que llega `CostoCampaniaAnulado` (con `sinEfecto` `true` o `false`), **entonces** se envía `RestaurarInsumos`; con `InsumosRestaurados`, S1 queda `COMPENSADA`.
6. **Dado** que llega `AnulacionCostoRechazada`, **entonces** **no** se restauran los insumos, S1 queda `REQUIERE_INTERVENCION` y L1 sigue `PENDIENTE_REVISION` con `motivo.codigo = ANULACION_COSTO_RECHAZADA`.
7. **Dado** que `AnularCostoCampania` no tiene respuesta, **cuando** vence el tiempo límite, **entonces** se reenvía sin límite de intentos, con espera creciente hasta 10 minutos, y `RestaurarInsumos` no se envía mientras no se conozca el resultado.

---

### Historia 4 — Compensar cuando inventario no responde (Prioridad: P1)

Como administrador, quiero que una labor cuyo descuento quedó en duda no deje stock descontado, aunque el descuento llegue tarde.

**Prueba independiente:** el inventario simulado no responde a `DescontarInsumos`.

**Escenarios de aceptación:**

1. **Dado** que `DescontarInsumos` se envió 4 veces sin respuesta, **entonces** `DESCONTAR_INSUMOS` queda `SIN_RESPUESTA`, L1 `PENDIENTE_REVISION` con `motivo.codigo = SIN_RESPUESTA_INVENTARIO`, S1 `COMPENSANDO` y se envía `RestaurarInsumos`. (Inventario rechaza un descuento tardío con `SAGA_COMPENSADA`.)
2. **Dado** que llega `InsumosRestaurados`, **entonces** S1 queda `COMPENSADA`; `RestaurarInsumos` sin respuesta se reenvía sin límite.

---

### Historia 5 — Procesar respuestas duplicadas, tardías y fallos sin perder nada (Prioridad: P1)

Como operador, quiero que los duplicados, las respuestas tardías y los fallos técnicos no cambien el resultado de la Saga ni pierdan mensajes (RN-09, RNF-11).

**Prueba independiente:** se publican respuestas repetidas y fuera de orden, y se simulan fallos de DynamoDB.

**Escenarios de aceptación:**

1. **Dado** que S1 ya avanzó con `InsumosDescontados`, **cuando** llega otro `InsumosDescontados` (mismo u otro `idMensaje`), **entonces** no se reenvía `RegistrarCostoCampania`, se agrega a `respuestasTardias` de S1 y L1 no cambia.
2. **Dado** que S1 está compensando por tiempo límite, **cuando** llega tarde `CostoCampaniaRegistrado`, **entonces** se registra como tardía y L1 sigue `PENDIENTE_REVISION`; el resultado lo decide la anulación en curso (constitución §6).
3. **Dado** que llega `InsumosRechazados` con `SAGA_COMPENSADA`, o `CostoCampaniaRechazado` con `SAGA_ANULADA`, **entonces** se registra como tardía, sin cambios en la labor.
4. **Dado** que DynamoDB falla al procesar una respuesta, **entonces** el mensaje se reintenta 3 veces (1 s, 2 s, 4 s) y, si sigue fallando, se publica en `servicio-operaciones.respuestas-saga.dlq` y se confirma. Nada se descarta en silencio.
5. **Dado** una respuesta con JSON inválido, sin `idMensaje` o `idCorrelacion`, con `tipo` desconocido, con `version` ≠ 1, con `datos.idSaga` ≠ `idCorrelacion` o de una Saga inexistente, **entonces** va a la DLQ sin reintentos, con log de error.

---

### Historia 6 — Recuperarse tras un reinicio del coordinador (Prioridad: P1)

Como operador, quiero que una Saga a medias continúe sola después de que el servicio se cae y vuelve (RNF-10).

**Prueba independiente:** se deja una Saga con un paso `ENVIADO` y la fecha límite vencida, sin mensaje en ninguna cola, y se ejecuta la tarea de recuperación.

**Escenarios de aceptación:**

1. **Dado** que el proceso se cayó después de guardar S1 y antes de publicar `DescontarInsumos`, **cuando** la tarea de recuperación encuentra S1 vencida, **entonces** publica `DescontarInsumos` (intento 2) y la Saga sigue normalmente.
2. **Dado** que el consumidor estuvo detenido con respuestas en la cola, **cuando** vuelve, **entonces** las procesa en orden y las Sagas terminan igual que sin la caída.
3. **Dado** dos ejecuciones simultáneas de la tarea de recuperación, **entonces** cada comando vencido se reenvía una sola vez (actualización condicional por `version`).
4. **Dado** que RabbitMQ no acepta la publicación, **entonces** la Saga queda guardada con su fecha límite y la tarea la reenvía cuando vence; la solicitud HTTP que la inició responde igual (`201`, labor `PENDIENTE`).

---

### Historia 7 — Consultar el estado de una Saga (Prioridad: P2)

Como administrador o gerente, quiero ver el detalle de cada paso de una Saga, para entender por qué una labor quedó en revisión (RNF-22).

**Escenarios de aceptación:**

1. **Dado** S1, **cuando** un administrador pide `GET /sagas/S1`, **entonces** recibe estado general, paso actual, costo y, por paso, estado, intentos, fechas, respuesta y error, más las respuestas tardías.
2. **Dado** un técnico de campo, **entonces** recibe `403 SIN_PERMISO`; **dado** un ID inexistente, `404 SAGA_NO_ENCONTRADA`.

---

### Casos borde

- `CostoCampaniaRegistrado` y el vencimiento del tiempo límite al mismo tiempo: gana la primera escritura condicional; si gana la respuesta, la Saga se completa; si gana el vencimiento, la respuesta queda como tardía y decide la anulación.
- `InsumosRechazados` que llega mientras la Saga compensa por falta de respuesta de inventario: se registra como tardía; la restauración responde `sinEfecto = true` y la Saga queda `COMPENSADA`.
- Una labor `PENDIENTE` con insumos, campaña `VALIDADA` y sin `idSaga`, creada antes de implementar esta spec (RQ-LAB-08): se le inicia la Saga con el comando `sagas:iniciar-pendientes`, que se ejecuta una vez al desplegar. Las que tienen la validación diferida las inicia la revalidación.
- Más de 20 respuestas tardías en una Saga: se guardan las 20 más recientes (límite de 400 KB por ítem de DynamoDB).
- `monto` que gestión rechaza por formato (`DATOS_INVALIDOS`): es un `CostoCampaniaRechazado` más; se compensa igual.

## Requisitos

### Requisitos funcionales

#### Inicio

- **RQ-SAG-01**: Cuando una labor queda `PENDIENTE` con insumos y la campaña validada, se crea la Saga (`idSaga` UUID nuevo) en la **misma** escritura que la labor, con el paso `DESCONTAR_INSUMOS` `ENVIADO` y su fecha límite, y después se publica `DescontarInsumos` (constitución §6: se persiste antes de enviar).

#### Comandos (contrato de los participantes)

- **RQ-SAG-02**: Todo comando usa el sobre común con `idMensaje` nuevo en cada envío, `idCorrelacion = idSaga`, `version = 1`, `origen = servicio-operaciones`, y se publica persistente en el exchange por defecto con el nombre de la cola como routing key, esperando la confirmación del broker:

  | `tipo` | Cola | `datos` |
  |---|---|---|
  | `DescontarInsumos` | `servicio-inventario.comandos` | `idSaga`, `idLabor`, `items: [{ idInsumo, cantidad }]` |
  | `RestaurarInsumos` | `servicio-inventario.comandos` | `idSaga`, `idLabor` |
  | `RegistrarCostoCampania` | `servicio-gestion.comandos` | `idSaga`, `idLabor`, `idCampania`, `monto` (el `costoTotal` recibido, sin cambios), `categoria = INSUMO` |
  | `AnularCostoCampania` | `servicio-gestion.comandos` | `idSaga`, `idLabor`, `idCampania` |

#### Respuestas y transiciones

- **RQ-SAG-03**: El servicio consume de `servicio-operaciones.respuestas-saga` las respuestas `InsumosDescontados`, `InsumosRechazados`, `InsumosRestaurados`, `CostoCampaniaRegistrado`, `CostoCampaniaRechazado`, `CostoCampaniaAnulado` y `AnulacionCostoRechazada`, con los `datos` de los contratos de inventario (RQ-SAG-09) y gestión (2.3).
- **RQ-SAG-04**: Transiciones por respuesta (el resto de combinaciones se registra en `respuestasTardias` sin otro efecto):

  | Saga / paso esperado | Respuesta | Efecto en la Saga | Labor | Comando siguiente |
  |---|---|---|---|---|
  | `EN_CURSO` / `DESCONTAR_INSUMOS` | `InsumosDescontados`, `costoTotal` > 0 | Guarda `costoTotal`; `REGISTRAR_COSTO` `ENVIADO` | — | `RegistrarCostoCampania` |
  | `EN_CURSO` / `DESCONTAR_INSUMOS` | `InsumosDescontados`, `"0.00"` | `REGISTRAR_COSTO` `OMITIDO`; `COMPLETADA` | `CONFIRMADA` | — |
  | `EN_CURSO` / `DESCONTAR_INSUMOS` | `InsumosRechazados` | `RECHAZADA` | `RECHAZADA` con el código de inventario | — |
  | `EN_CURSO` / `REGISTRAR_COSTO` | `CostoCampaniaRegistrado` | `COMPLETADA` | `CONFIRMADA` | — |
  | `EN_CURSO` / `REGISTRAR_COSTO` | `CostoCampaniaRechazado` | `COMPENSANDO`; `RESTAURAR_INSUMOS` `ENVIADO` | `PENDIENTE_REVISION` (`COSTO_RECHAZADO`) | `RestaurarInsumos` |
  | `COMPENSANDO` / `ANULAR_COSTO` | `CostoCampaniaAnulado` | `RESTAURAR_INSUMOS` `ENVIADO` | — | `RestaurarInsumos` |
  | `COMPENSANDO` / `ANULAR_COSTO` | `AnulacionCostoRechazada` | `REQUIERE_INTERVENCION` | `motivo` → `ANULACION_COSTO_RECHAZADA` | — |
  | `COMPENSANDO` / `RESTAURAR_INSUMOS` | `InsumosRestaurados` | `COMPENSADA` | — | — |

  El paso que recibe su respuesta queda `COMPLETADO` (o `RECHAZADO` si la respuesta es un rechazo), con la fecha y un resumen de la respuesta.
- **RQ-SAG-05**: Tiempo límite (tarea de recuperación, RQ-SAG-09):

  | Paso vencido | Envíos hechos | Efecto |
  |---|---|---|
  | `DESCONTAR_INSUMOS` o `REGISTRAR_COSTO` | < 4 | Se reenvía el mismo comando |
  | `DESCONTAR_INSUMOS` | 4 | Paso `SIN_RESPUESTA`; Saga `COMPENSANDO`; labor `PENDIENTE_REVISION` (`SIN_RESPUESTA_INVENTARIO`); se envía `RestaurarInsumos` |
  | `REGISTRAR_COSTO` | 4 | Paso `SIN_RESPUESTA`; Saga `COMPENSANDO`; labor `PENDIENTE_REVISION` (`SIN_RESPUESTA_GESTION`); se envía `AnularCostoCampania` |
  | `ANULAR_COSTO` o `RESTAURAR_INSUMOS` | Cualquiera | Se reenvía sin límite; la espera se duplica en cada envío hasta 10 minutos |

- **RQ-SAG-06**: Tiempo límite por paso y número de envíos configurables: `SAGA_TIEMPO_LIMITE_SEGUNDOS` (por defecto 30), `SAGA_MAXIMO_ENVIOS` (por defecto 4, es decir, 1 + 3 reintentos) y `SAGA_ESPERA_MAXIMA_COMPENSACION_SEGUNDOS` (por defecto 600).
- **RQ-SAG-07**: Todo cambio de la Saga, de la labor y su auditoría se escriben juntos (README D-08) y condicionados a la `version` de la Saga; el comando siguiente se publica después.

#### Mensajes recibidos

- **RQ-SAG-08**: Validación del sobre de una respuesta: JSON interpretable, `idMensaje` e `idCorrelacion` UUID, `tipo` de RQ-SAG-03, `version = 1`, `datos.idSaga = idCorrelacion` y Saga existente. Si no, va a la DLQ sin reintentos (README D-13). Los fallos técnicos se reintentan 3 veces con espera creciente y luego van a la DLQ (README D-14).

#### Recuperación

- **RQ-SAG-09**: Una tarea programada cada 10 segundos busca las Sagas no terminales con `fechaLimite` vencida y aplica RQ-SAG-05 (RNF-10). Un reinicio del proceso no pierde nada: el estado está en DynamoDB y los mensajes no confirmados vuelven a la cola.

#### Estado y consulta

- **RQ-SAG-10**: Estados: `EN_CURSO` y `COMPENSANDO` (activos); `COMPLETADA`, `RECHAZADA`, `COMPENSADA` y `REQUIERE_INTERVENCION` (terminales). Por paso: `ENVIADO`, `COMPLETADO`, `RECHAZADO`, `OMITIDO`, `SIN_RESPUESTA`.
- **RQ-SAG-11**: Por paso se guarda estado, intentos, fecha del primer y último envío, fecha de respuesta, resumen de la respuesta (`tipo`, `codigo`, `motivo`) y error (RNF-22).
- **RQ-SAG-12**: `GET /sagas/{id}` devuelve la Saga completa (roles `administrador`, `gerencia`, `lectura_operaciones`), o `404 SAGA_NO_ENCONTRADA`.
- **RQ-SAG-13**: Los logs de cada mensaje enviado o recibido incluyen `idCorrelacion`, `idMensaje`, `tipo` y resultado. La auditoría usa el actor `servicio-operaciones` y las acciones `INICIAR_SAGA`, `AVANZAR_SAGA` y `ACTUALIZAR_LABOR_SAGA`.

### Entidades clave

- **Saga**: `idSaga`, `idLabor`, `idCampania`, `items`, `estado` (`EstadoSaga`), `pasoActual`, `costoTotal`, `pasos` (mapa `PasoSaga` → `EstadoPasoSaga`), `respuestasTardias`, `fechaLimite`, `version`, `fechaCreacion`, `fechaActualizacion`.
- **PasoSaga**: `DESCONTAR_INSUMOS` / `REGISTRAR_COSTO` / `ANULAR_COSTO` / `RESTAURAR_INSUMOS`.
- **EstadoSaga** y **EstadoPaso**: RQ-SAG-10 (glosario de la constitución v2.8.0).
- **LaborAgricola**: usa `idSaga` y `motivo` (`spec-labores.md`).

## Criterios de éxito

- **CE-SAG-01**: Tests obligatorios de la Saga de la constitución §8 en verde: éxito, costo total `0.00` sin registro de costo, stock insuficiente, fallo al registrar costo con compensación, tiempo límite en el registro de costo con anulación seguida de restauración, anulación rechazada sin restauración, anulación sin respuesta sin restauración, mensaje duplicado y recuperación tras reinicio del coordinador.
- **CE-SAG-02**: Ninguna respuesta termina sin aplicarse, registrarse como tardía o estar en la DLQ.
- **CE-SAG-03**: Con 50 labores con insumos registradas en paralelo y participantes simulados, todas terminan `CONFIRMADA` y cada participante recibe un solo comando por `idSaga` (sin vencimientos).
- **CE-SAG-04**: Una Saga sin fallos termina en menos de 5 s desde el registro de la labor (participantes que responden en menos de 1 s, CE-SAG-05 de inventario y gestión).
- **CE-SAG-05**: Prueba de extremo a extremo en Docker Compose (perfiles `saga`, `gateway` y `auth`) con inventario y gestión reales: una labor con stock suficiente queda `CONFIRMADA` con el stock descontado y el costo registrado; con stock insuficiente queda `RECHAZADA`. Requiere `api-gateway` para la consulta de campaña (README AP-04); mientras no exista, la labor queda con validación diferida y la Saga no arranca.

## Supuestos

- Los participantes responden siempre a la cola `servicio-operaciones.respuestas-saga` con el mismo `idCorrelacion` y no llaman a este servicio.
- El tiempo límite de 30 s es holgado frente al objetivo de 1 s por comando de los participantes.

## Aclaraciones

- **AC-01** — Resuelta (contrato de inventario, AC-03 de `spec-descuento-saga.md`): se adopta RQ-SAG-09 de inventario tal cual.
- **AC-02** — Resuelta (contrato de gestión, 2.3 de `spec-costo-saga.md`): se adoptan los seis mensajes tal cual; el `monto` es el `costoTotal` de inventario.
- **AC-03** — Resuelta (constitución v2.8.0): `EstadoSaga`, `PasoSaga`, `EstadoPaso`, los mensajes y la DLQ de respuestas están en el glosario.

## Fuera de alcance

- Sagas con otros pasos (por ejemplo, labores con costo de mano de obra).
- Reprocesar mensajes de la DLQ (se hace a mano desde el panel de RabbitMQ).
- Resolver labores en revisión (`spec-revision-labores.md`).

---

# 2. Plan

Primera funcionalidad con RabbitMQ: aquí se agregan la conexión, el publicador y el consumidor. Reutiliza la base de `spec-labores.md`.

## 2.1 Dependencias y configuración

- Se agrega `php-amqplib/php-amqplib`.
- `config/rabbitmq.php`: `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`, `RABBITMQ_VHOST` y `RABBITMQ_SSL` (`AMQPSSLConnection` si es `true`, para AMQPS en la nube). `config/saga.php`: las variables de RQ-SAG-06.
- `/salud/readiness` pasa a incluir RabbitMQ (abre y cierra una conexión con tiempo límite de 2 s).
- `docker-compose.yml`: nuevo `servicio-operaciones-consumidor` (misma imagen, volumen y variables), comando `php artisan operaciones:consumir-respuestas`, `restart: unless-stopped`, `mem_limit: 128m` y `depends_on: servicio-operaciones: condition: service_healthy`, igual que el programador (`spec-labores.md` 2.1).
- Las tablas pasan a incluir `sagas` en `tablas.json`.

## 2.2 Colas

| Cola | Dueño | Declaración (README D-13) |
|---|---|---|
| `servicio-inventario.comandos` | `servicio-inventario` | Durable, `x-dead-letter-exchange: ""`, `x-dead-letter-routing-key: servicio-inventario.comandos.dlq` |
| `servicio-gestion.comandos` | `servicio-gestion` | Durable, `x-dead-letter-exchange: ""`, `x-dead-letter-routing-key: servicio-gestion.comandos.dlq` |
| `servicio-operaciones.respuestas-saga` | Este servicio | Durable, sin argumentos |
| `servicio-operaciones.respuestas-saga.dlq` | Este servicio | Durable, sin argumentos |

Este servicio declara también las colas de los participantes (con sus mismos argumentos) para que un comando no se pierda si el participante todavía no arrancó: sin la cola, el exchange por defecto descartaría el mensaje. Las DLQ de los participantes las declaran ellos.

## 2.3 Publicador

`PublicadorRabbitMq` (`Infrastructure/Messaging`) implementa `PublicadorMensajes`:

- `enviarComando(cola, tipo, datos, idCorrelacion): idMensaje`: arma el sobre (`idMensaje` nuevo, `fechaOcurrencia`, `origen`, `version = 1`), publica con `delivery_mode = 2` y `content_type = application/json` en un canal con `confirm_select()`, y espera la confirmación con `wait_for_pending_acks(5)`. Si no confirma, lanza `PublicacionFallida`.
- La conexión se abre al primer uso y se reutiliza; si está caída, se reabre una vez.
- Los casos de uso capturan `PublicacionFallida`, la registran en el log y **no** cambian la respuesta: la Saga ya está guardada con su fecha límite (Historia 6, escenario 4).

## 2.4 Consumidor

`operaciones:consumir-respuestas` (`InterfaceAdapters/Console`) con `ConsumidorRespuestasSaga` (`InterfaceAdapters/Messaging`):

```text
canal con prefetch 1, ack manual
por cada mensaje:
  1. Interpretar y validar el sobre (RQ-SAG-08)
       falla → publicar el cuerpo original en la DLQ (con header "motivo"), ack, log de error. Sin reintentos.
  2. intentos = 0
     loop:
       try:
         resultado = ProcesarRespuestaSaga.ejecutar(sobre)      ← lee, decide y escribe (RQ-SAG-07)
         publicar resultado.comandoSiguiente si hay              ← PublicacionFallida: solo log
         ack; break
       catch ConflictoEscritura: releer y volver a decidir (hasta 5 veces; luego, como error técnico)
       catch error técnico:
         intentos++
         si intentos > 3 → DLQ, ack, log de error; break
         esperar 1 s, 2 s, 4 s
```

- Con `prefetch 1` las respuestas se procesan de a una: más simple y suficiente para el volumen del examen.
- Si la conexión se pierde, el comando termina con código de error y Docker lo reinicia (`restart: unless-stopped`); los mensajes no confirmados vuelven a la cola.
- Los tests usan `procesar(maximo, segundosEspera)` en el mismo proceso, en lugar del bucle infinito, y esperas de 10, 20 y 40 ms.

## 2.5 Máquina de estados

`Saga` (`Domain/Saga`) es la única que decide. Métodos puros, sin infraestructura:

- `Saga::iniciar(idSaga, labor, ahora, config): Saga` → paso `DESCONTAR_INSUMOS` `ENVIADO`.
- `aplicarRespuesta(tipo, datos, ahora, config): Decision` → la tabla de RQ-SAG-04.
- `vencer(ahora, config): Decision` → la tabla de RQ-SAG-05.

`Decision` lleva el cambio de la labor (estado nuevo y motivo, o nada), el comando a enviar (o nada) y si la respuesta fue tardía. Los casos de uso solo leen, llaman a la Saga, escriben con la unidad de trabajo y publican.

Fecha límite: `ahora + tiempoLimite` en los pasos hacia adelante; en compensación, `ahora + min(tiempoLimite × 2^(envíos − 1), esperaMaxima)`.

## 2.6 Modelo de datos

Tabla `sagas` (clave `id_saga`):

| Atributo | Tipo | Nota |
|---|---|---|
| `id_saga`, `id_labor`, `id_campania` | `S` | |
| `estado`, `paso_actual` | `S` | |
| `items` | `L` de `M` `{ id_insumo, cantidad }` | Para reenviar `DescontarInsumos` |
| `costo_total` | `S` | Tras `InsumosDescontados` |
| `pasos` | `M` de `PasoSaga` → `M` `{ estado, intentos, fecha_primer_envio, fecha_ultimo_envio, fecha_respuesta, respuesta: { tipo, codigo, motivo }, error }` | RQ-SAG-11 |
| `respuestas_tardias` | `L` de `M` `{ tipo, id_mensaje, codigo, fecha_recepcion }` | Hasta 20 |
| `activa` | `S` = `"1"` | Solo en `EN_CURSO` y `COMPENSANDO` (índice disperso) |
| `fecha_limite` | `S` | ISO 8601 UTC |
| `version` | `N` | |
| `fecha_creacion`, `fecha_actualizacion` | `S` | |

Índice `gsi_activas`: partición `activa`, orden `fecha_limite`. La recuperación hace `Query activa = "1" AND fecha_limite <= :ahora` (hasta 100 por ejecución); al pasar a un estado terminal se quita `activa`.

## 2.7 Casos de uso

| Carpeta | Clase | Responsabilidad |
|---|---|---|
| `Application/UseCases/Saga` | `IniciarSaga.php` | Lo llaman `RegistrarLaborCasoUso`, `RealizarLaborCasoUso` y `RevalidarCampaniasCasoUso` **dentro** de su unidad de trabajo: agrega el `Put` de la Saga y devuelve el comando a publicar tras el commit |
| `Application/UseCases/Saga` | `ProcesarRespuestaSaga.php` | Despacha a los manejadores por `tipo` |
| `Application/UseCases/Saga` | `ManejarInsumosDescontados.php`, `ManejarInsumosRechazados.php`, `ManejarCostoRegistrado.php`, `ManejarCostoRechazado.php`, `ManejarCostoAnulado.php`, `ManejarAnulacionRechazada.php`, `ManejarInsumosRestaurados.php` | Convierten `datos` en la entrada de `Saga::aplicarRespuesta`; la decisión es del dominio |
| `Application/UseCases/Saga` | `ReanudarSagasEstancadas.php` | RQ-SAG-09 |
| `Application/UseCases/Saga` | `IniciarSagasPendientes.php` | Caso borde de las labores `PENDIENTE` sin Saga |
| `Application/UseCases/Saga` | `ConsultarSagaCasoUso.php` | RQ-SAG-12 |

La constitución nombra un manejador por respuesta; se agrega `ManejarInsumosRestaurados`, que no figura en la lista de referencia.

Ajustes respecto del plan original:

- Los siete manejadores se reemplazaron por `LectorRespuesta` (valida y traduce los `datos` de cada tipo según el contrato del participante) y `AvanceSaga` (relee, deja decidir a la Saga, escribe Saga, labor y auditoría juntas, y publica). Cada manejador solo habría leído campos; la decisión ya es del dominio. `ProcesarRespuestaSaga` y `ReanudarSagasEstancadas` usan el mismo `AvanceSaga`, así que la respuesta y el vencimiento comparten la relectura ante conflictos.
- El comando siguiente lo publica Application (`EnvioComandos`) después de confirmar la escritura, no el consumidor; así el inicio de la Saga desde el registro, la realización y la revalidación de labores publica igual. Una `PublicacionFallida` solo se registra: la recuperación reenvía.
- El consumidor (`InterfaceAdapters/Messaging`) no depende de `php-amqplib`: recibe el cuerpo del mensaje de `FuenteMensajes`, cuya implementación (`FuenteMensajesRabbitMq`) confirma o publica en la DLQ con los headers `x-motivo` y `x-cola-origen`. Si la DLQ no confirma, el mensaje no se confirma y vuelve a la cola.
- `ConexionRabbitMq` usa un canal de publicación en modo confirmación (una sola vez por canal) y canales aparte para consumir; heartbeat de 30 s, atendido mientras el consumidor espera mensajes.
- `PasoSaga`, `Participante` y `TipoRespuesta` son enumeraciones del dominio: la infraestructura traduce el participante a su cola (`TopologiaSaga::colaDe`).
- `LaborAgricola::iniciarSaga` no sube la versión, porque se guarda en la misma escritura que la creación o el cambio que la origina; `sagas:iniciar-pendientes` usa `confirmarCambioAparte`, para que dos ejecuciones simultáneas no inicien dos Sagas.
- Una tabla nueva en `tablas.json` exige volver a ejecutar `php artisan dynamodb:crear-tablas` al desplegar. En Docker Compose lo hace el arranque de `servicio-operaciones` (basta reiniciarlo); sin la tabla, la escritura falla completa y no queda la labor a medias. Se detectó en la verificación de T10.
- Tests: el vhost `pruebas` lo crea `tests/bootstrap.php` con la API de administración de RabbitMQ (`RABBITMQ_GESTION_URL`); `FlujoSaga` vacía la tabla `sagas` al empezar cada escenario, porque la recuperación atiende todas las Sagas vencidas y una dejada activa por otro test reenviaría comandos ajenos; RabbitMQ 4 informa `x-queue-type: classic` en todas las colas, y el test de topología lo ignora.

## 2.8 Diseño por capas

| Capa | Archivo | Responsabilidad |
|---|---|---|
| `Domain/Saga` | `Saga.php`, `PasoSaga.php`, `EstadoSaga.php`, `EstadoPaso.php`, `Decision.php`, `ConfiguracionSaga.php`, `RepositorioSaga.php` | 2.5 |
| `Application/Contracts` | `PublicadorMensajes.php` | `enviarComando` |
| `InterfaceAdapters/Messaging` | `ConsumidorRespuestasSaga.php`, `SobreMensaje.php` | 2.4 |
| `InterfaceAdapters/Console` | `ConsumirMensajesComando.php`, `ReanudarSagasComando.php`, `IniciarSagasPendientesComando.php` | `operaciones:consumir-respuestas`, `sagas:reanudar` (cada 10 s, `withoutOverlapping`), `sagas:iniciar-pendientes` |
| `InterfaceAdapters/Http` | `SagaControlador.php`, `Resources/SagaRecurso.php` | `GET /sagas/{id}` |
| `Infrastructure/Messaging` | `ConexionRabbitMq.php`, `TopologiaSaga.php`, `PublicadorRabbitMq.php` | 2.2 y 2.3 |
| `Infrastructure/Persistence/DynamoDb` | `RepositorioSagaDynamo.php`, `Mappers/SagaMapper.php` | 2.6 |

## 2.9 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `tests/Unit/Domain/Saga/SagaTest.php` | Cada fila de RQ-SAG-04 y RQ-SAG-05, respuestas tardías, límite de 20, cálculo de fecha límite |
| Unitario | `tests/Unit/Application/Saga/ProcesarRespuestaSagaTest.php` | Con dobles: conflicto de escritura con relectura, publicación fallida sin cambiar el resultado |
| Integración | `tests/Integration/Messaging/SagaExitoTest.php` | Historia 1, incluido costo `0.00` |
| Integración | `tests/Integration/Messaging/SagaRechazoTest.php` | Historia 2 |
| Integración | `tests/Integration/Messaging/SagaCompensacionTest.php` | Historias 3 y 4 con reloj fijo: rechazo de costo, tiempo límite con anulación y restauración, anulación rechazada sin restauración, anulación sin respuesta sin restauración |
| Integración | `tests/Integration/Messaging/SagaDuplicadosTest.php` | Historia 5, escenarios 1 a 3 |
| Integración | `tests/Integration/Messaging/SagaFallosTest.php` | Historia 5, escenarios 4 y 5: repositorio que falla → 4 intentos y DLQ; sobres inválidos → DLQ sin reintentos |
| Integración | `tests/Integration/Messaging/SagaRecuperacionTest.php` | Historia 6 |
| Integración | `tests/Integration/Messaging/SagaConcurrenciaTest.php` | CE-SAG-03 (registro con `EnParalelo`) y el caso borde de respuesta y vencimiento simultáneos; dos ejecuciones simultáneas de la recuperación (Historia 6, escenario 3) |
| Integración | `tests/Integration/Messaging/TopologiaTest.php` | Las cuatro colas con sus argumentos; declarar después de inventario y gestión no falla |
| Integración | `tests/Integration/Http/SagasTest.php` | Historia 7 |

Los tests de mensajería usan el vhost `pruebas` (README D-17): hacen de participantes leyendo `servicio-inventario.comandos` y `servicio-gestion.comandos` y publicando en `servicio-operaciones.respuestas-saga`. Cada test purga las colas al empezar. La prueba de extremo a extremo (CE-SAG-05) se hace a mano en Docker Compose y se documenta en el README del servicio.

---

# 3. Tareas

- [x] **T01** — Agregar `php-amqplib`, `ConexionRabbitMq`, `TopologiaSaga`, la configuración y RabbitMQ en readiness. *Hecho cuando:* pasa `TopologiaTest.php`.
- [x] **T02** — Implementar `PublicadorRabbitMq` con confirmaciones.
- [x] **T03** — Crear `Saga`, sus enumeraciones, `Decision` y `ConfiguracionSaga`, con `SagaTest.php`.
- [x] **T04** — Agregar `sagas` a `tablas.json` e implementar `RepositorioSagaDynamo` con su mapper.
- [x] **T05** — Implementar `IniciarSaga` y conectarlo a registro, realización y revalidación de labores. *Hecho cuando:* pasa el escenario 1 (y 5) de la Historia 1.
- [x] **T06** — Implementar `ConsumidorRespuestasSaga`, `operaciones:consumir-respuestas`, `ProcesarRespuestaSaga` y los manejadores. *Hecho cuando:* pasan `SagaExitoTest.php`, `SagaRechazoTest.php`, `SagaDuplicadosTest.php` y `SagaFallosTest.php`.
- [x] **T07** — Implementar `ReanudarSagasEstancadas` y `sagas:reanudar`. *Hecho cuando:* pasan `SagaCompensacionTest.php` y `SagaRecuperacionTest.php`.
- [x] **T08** — Implementar `GET /sagas/{id}`, `sagas:iniciar-pendientes` y `SagaConcurrenciaTest.php`; documentar en `openapi.yaml`.
- [ ] **T09** — Agregar `servicio-operaciones-consumidor` a `docker-compose.yml`. Cuando exista `api-gateway`, hacer la prueba de extremo a extremo de CE-SAG-05; hasta entonces queda pendiente y se anota aquí. Hecho: el consumidor corre en Compose (perfiles `operaciones`, `saga`, `backend`, `todo`). Pendiente: la prueba completa por HTTP, que necesita `api-gateway` y el realm de Keycloak.
- [x] **T10** — Verificar con inventario y gestión que los contratos se consumen sin cambios y marcar el T09 de `servicio-inventario/specs/spec-descuento-saga.md` (README AP-05). Verificado (2026-11-03) en Docker Compose con el perfil `saga`, con inventario y gestión reales y solo la consulta de campaña simulada: labor con stock y campaña existente → `CONFIRMADA` (costo 48,50 registrado en gestión, stock 100 → 90); campaña inexistente en gestión → `CostoCampaniaRechazado` (`CAMPANIA_NO_ENCONTRADA`), `RestaurarInsumos` y Saga `COMPENSADA` (el stock vuelve); insumo inexistente → `InsumosRechazados` (`INSUMO_NO_ENCONTRADO`) y labor `RECHAZADA`.
- [x] **T11** — Verificación final: `vendor/bin/pest --coverage --min=80` en verde y criterios CE-SAG-01 a CE-SAG-05 cubiertos. CE-SAG-05 queda cubierto en su parte de mensajería por T10; la parte HTTP depende de T09. Pipeline en verde en GitHub Actions (2026-11-03), con RabbitMQ como contenedor de servicio.
