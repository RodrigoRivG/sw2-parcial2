# Descuento y restauración de insumos en la Saga — `servicio-inventario`

| Campo | Valor |
|---|---|
| Servicio | `servicio-inventario` |
| Archivo | `specs/spec-descuento-saga.md` |
| Estado | Spec aprobada (2026-11-02) · Implementada (2026-11-02) |
| Constitución | v2.8.0 (secciones 4, 5, 6 y 8) |
| Trazabilidad | CU-08 (prioridad media; incluido por CU-12 como paso 2) · RF-10 (y RF-13 del coordinador) · RN-04, RN-07, RN-08, RN-09 · RNF-10, RNF-11, RNF-22 |
| Depende de | `spec-movimientos.md` (operación común de stock), `spec-stock-bajo.md` (conexión a RabbitMQ y evento) |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Contexto

Cuando un técnico registra una labor realizada con insumos, `servicio-operaciones` (coordinador) ejecuta la Saga (RN-07). El primer paso es este servicio: descontar los insumos y calcular su costo. Con ese costo, el coordinador pide a `servicio-gestion` que lo registre en la campaña. Este servicio es **participante**: recibe comandos, responde y no llama a nadie (constitución §5).

```text
servicio-operaciones ──DescontarInsumos──▶ servicio-inventario
servicio-operaciones ◀──InsumosDescontados (costoTotal) / InsumosRechazados──

(gestión rechazó el costo, o lo anuló tras un tiempo límite)
servicio-operaciones ──RestaurarInsumos──▶ servicio-inventario
servicio-operaciones ◀──InsumosRestaurados──
```

El coordinador puede enviar `RestaurarInsumos` antes de que llegue un `DescontarInsumos` que seguía en la cola. Por eso una restauración sin descuento previo deja el `idSaga` marcado, y el descuento tardío se rechaza con `SAGA_COMPENSADA` (constitución v2.6.0).

## Escenarios de usuario y pruebas

### Historia 1 — Descontar los insumos de una labor (Prioridad: P1)

Como sistema coordinador de la Saga, quiero que los insumos de una labor se descuenten del stock y se calcule su costo, para registrarlo en la campaña (RF-10).

**Por qué esta prioridad:** es el primer paso de la Saga; sin él ninguna labor con insumos se confirma.

**Prueba independiente:** se publica el comando en `servicio-inventario.comandos` (Testcontainers) y se verifican stock, movimientos y la respuesta en `servicio-operaciones.respuestas-saga`.

**Escenarios de aceptación:**

1. **Dado** "Urea" (stock 200 kg, costo `"4.85"`) y "Glifosato" (stock 50 L, costo `"38.20"`), **cuando** llega `DescontarInsumos` con `idSaga` S1, `idLabor` L1 e `items` `[{ Urea, "100" }, { Glifosato, "2.5" }]`, **entonces** el stock queda en 100 kg y 47,5 L, se crean dos movimientos `SALIDA` con `idSaga` S1, `idLabor` L1 y motivo "Labor L1", y se publica `InsumosDescontados` con `costoTotal` `"580.50"` (485,00 + 95,50) e `idCorrelacion` = S1.
2. **Dado** un costo total de precisión mayor, como 3 kg × `"0.1235"` = 0,3705, **entonces** `costoTotal` es `"0.37"`; con 1 kg × `"0.1250"` es `"0.13"` (mitad hacia arriba, solo al final).
3. **Dado** insumos con costo unitario 0, **entonces** se descuentan y `costoTotal` es `"0.00"` (el coordinador no envía el costo a gestión; constitución de operaciones v2.5.0).
4. **Dado** que "Glifosato" tiene solo 2 L y el comando pide 2,5 L, **entonces** no se descuenta ningún insumo (tampoco la urea) y se publica `InsumosRechazados` con código `STOCK_INSUFICIENTE` e `insumosAfectados` `[{ idInsumo: Glifosato, cantidadSolicitada: "2.500", stockDisponible: "2.000" }]` (RN-04).
5. **Dado** un `idInsumo` inexistente en `items`, **entonces** no se descuenta nada y se publica `InsumosRechazados` con `INSUMO_NO_ENCONTRADO` y ese insumo con `stockDisponible = null`.
6. **Dado** `items` vacío, o el mismo `idInsumo` dos veces, **entonces** se publica `InsumosRechazados` con `DATOS_INVALIDOS` sin tocar el stock.
7. **Dado** que S1 fue restaurado sin descuento previo (Historia 3, escenario 2), **cuando** llega `DescontarInsumos` con S1, **entonces** no se toca el stock y se publica `InsumosRechazados` con `SAGA_COMPENSADA`.

---

### Historia 2 — Procesar comandos duplicados sin descontar dos veces (Prioridad: P1)

Como sistema coordinador, quiero poder reenviar el comando (por reintento o recuperación tras un reinicio) sin que el stock se descuente dos veces (RN-09).

**Por qué esta prioridad:** RabbitMQ entrega "al menos una vez" y el coordinador reintenta.

**Prueba independiente:** se envía el mismo comando varias veces y se verifica un único descuento y respuestas iguales.

**Escenarios de aceptación:**

1. **Dado** que S1 ya se descontó, **cuando** llega otra vez `DescontarInsumos` con S1 (mismo o distinto `idMensaje`), **entonces** el stock no cambia y se publica de nuevo `InsumosDescontados` con los mismos `costoTotal` e `items`.
2. **Dado** lo mismo, pero con el costo unitario de "Urea" cambiado entre el primer comando y el repetido, **entonces** la respuesta repetida trae el costo original (constitución §4).
3. **Dado** que S2 fue rechazado por `STOCK_INSUFICIENTE`, **cuando** llega otra vez, aunque ahora sí haya stock, **entonces** se publica el mismo `InsumosRechazados` y no se descuenta nada.
4. **Dado** un comando repetido con otros `items`, **entonces** se responde el resultado original y se registra una advertencia en el log con el `idCorrelacion`.
5. **Dado** dos copias del mismo comando procesadas en paralelo, **entonces** el stock se descuenta una sola vez y ambas producen la misma respuesta.

---

### Historia 3 — Restaurar los insumos cuando el coordinador compensa (Prioridad: P1)

Como sistema coordinador, quiero devolver al stock los insumos de una Saga que no pudo completarse, para que el inventario no pierda lo que la labor no consumió (RN-08).

**Por qué esta prioridad:** sin compensación, cada costo rechazado en gestión deja stock perdido.

**Prueba independiente:** se publica `RestaurarInsumos` antes y después de `DescontarInsumos` y se verifican stock, movimientos y respuesta.

**Escenarios de aceptación:**

1. **Dado** que S1 descontó 100 kg de urea y 2,5 L de glifosato, **cuando** llega `RestaurarInsumos` con S1, **entonces** se crean dos movimientos `ENTRADA` por exactamente esas cantidades, con `idSaga` S1 y motivo "Compensación de saga S1", el stock vuelve a 200 kg y 50 L, S1 queda `RESTAURADO` y se publica `InsumosRestaurados` con `sinEfecto = false` y las cantidades restauradas.
2. **Dado** que S3 nunca llegó a descontar, **cuando** llega `RestaurarInsumos` con S3, **entonces** no hay movimientos, S3 queda `RESTAURADO` y se publica `InsumosRestaurados` con `sinEfecto = true`.
3. **Dado** que S2 fue rechazado, **cuando** llega `RestaurarInsumos` con S2, **entonces** se publica `InsumosRestaurados` con `sinEfecto = true` y S2 conserva el resultado `RECHAZADO`.
4. **Dado** que S1 ya fue restaurado, **cuando** llega otra vez `RestaurarInsumos` con S1, **entonces** no hay movimientos nuevos y se publica la misma respuesta de la primera vez.
5. **Dado** que S1 ya fue restaurado, **cuando** llega otra vez `DescontarInsumos` con S1, **entonces** se repite el `InsumosDescontados` original (un comando repetido devuelve la misma respuesta) y el stock no cambia. El coordinador la registra como respuesta tardía (constitución de operaciones §6).
6. **Dado** que entre el descuento y la restauración el costo unitario cambió, **entonces** las entradas de compensación guardan el costo unitario de las salidas originales.

---

### Historia 4 — Manejar fallos técnicos sin perder mensajes (Prioridad: P1)

Como operador, quiero que un fallo técnico no pierda el comando ni produzca una respuesta falsa, para poder diagnosticar y reprocesar (RNF-11).

**Prueba independiente:** con el repositorio simulado para fallar, se verifican los reintentos y el paso a la Dead Letter Queue.

**Escenarios de aceptación:**

1. **Dado** que MongoDB no responde, **cuando** llega un comando, **entonces** no se publica respuesta, el mensaje se reintenta 3 veces con espera creciente y, si sigue fallando, va a `servicio-inventario.comandos.dlq`.
2. **Dado** un mensaje cuyo sobre no se puede interpretar (JSON inválido, sin `idMensaje` o sin `idCorrelacion`) o con un `tipo` desconocido, **entonces** va a la DLQ sin reintentos, con log de error.
3. **Dado** un sobre válido con `datos` inválidos (cantidad como número JSON, cantidad 0, `idCorrelacion` distinto de `idSaga`, `version` distinta de 1), **entonces** se publica `InsumosRechazados` con `DATOS_INVALIDOS`: es un rechazo de negocio, no un fallo técnico.

---

### Casos borde

- Descuento de la Saga y salida manual simultáneos sobre el mismo insumo: nunca stock negativo; el perdedor recibe `STOCK_INSUFICIENTE` (por mensaje o por HTTP).
- Dos Sagas distintas que descuentan el mismo insumo con stock para una sola: una `InsumosDescontados` y otra `InsumosRechazados` con `STOCK_INSUFICIENTE` (test de concurrencia obligatorio, constitución §6).
- `DescontarInsumos` y `RestaurarInsumos` del mismo `idSaga` en paralelo: se procesan uno después del otro. Si el descuento entra primero, la restauración lo devuelve; si la restauración entra primero, el descuento se rechaza con `SAGA_COMPENSADA`. El stock final es el mismo en ambos órdenes.
- Cantidad con decimales para un insumo con unidad `UNIDAD`: `InsumosRechazados` con `DATOS_INVALIDOS` y ese insumo en `insumosAfectados`.
- `RestaurarInsumos` con un `idLabor` distinto del guardado: manda el `idSaga`; se restaura lo de ese `idSaga` y se registra una advertencia.
- Falla la publicación de la respuesta después del commit: el mensaje se reintenta; por idempotencia no hay efectos nuevos y la respuesta se publica en el reintento.
- El descuento deja un insumo bajo el mínimo: se evalúa el evento de stock bajo después de publicar la respuesta (`spec-stock-bajo.md`); su falla no afecta a la Saga.

## Requisitos

### Requisitos funcionales

#### Descuento

- **RQ-SAG-01**: El servicio debe consumir `DescontarInsumos` (versión 1) de la cola `servicio-inventario.comandos`, con el sobre común y `datos`:

  ```json
  {
    "idSaga": "uuid",
    "idLabor": "uuid",
    "items": [
      { "idInsumo": "uuid", "cantidad": "100" },
      { "idInsumo": "uuid", "cantidad": "2.5" }
    ]
  }
  ```

- **RQ-SAG-02**: Validaciones, en este orden:
  1. Sobre interpretable con `idMensaje`, `idCorrelacion` y `tipo` conocido; si no, DLQ sin reintentos.
  2. Formato de `datos`: `version = 1`, `idSaga` e `idLabor` UUID, `idCorrelacion = idSaga`, `items` con al menos un elemento, `idInsumo` UUID sin repetir, `cantidad` texto decimal > 0 con hasta 3 decimales; si no, `InsumosRechazados` con `DATOS_INVALIDOS` (no se guarda resultado).
  3. Estado del `idSaga` (tabla de RQ-SAG-05).
  4. Todos los insumos existen; si no, `INSUMO_NO_ENCONTRADO` con los faltantes.
  5. Cantidades enteras para insumos con unidad `UNIDAD`; si no, `DATOS_INVALIDOS` con esos insumos.
  6. Stock suficiente para todos; si no, `STOCK_INSUFICIENTE` con todos los insumos que no alcanzan.

  Los rechazos de los pasos 4 a 6 se guardan como `RECHAZADO`.
- **RQ-SAG-03**: Es todo o nada (constitución §5): si pasa las validaciones, se registra en una sola transacción una `SALIDA` por ítem (con la operación atómica condicionada de `spec-movimientos.md`), con `idSaga`, `idLabor`, motivo "Labor {idLabor}" y actor = `origen` del mensaje; se guarda el resultado `DESCONTADO` y la auditoría de cada movimiento (`DESCONTAR_INSUMOS_SAGA`).
- **RQ-SAG-04**: `costoTotal` = Σ (`cantidad` × `costoUnitario` vigente) con precisión completa, redondeado al final a 2 decimales, mitad hacia arriba (constitución §5).
- **RQ-SAG-05**: Efecto de `DescontarInsumos` según el estado del `idSaga`:

  | Estado del `idSaga` | Efecto | Respuesta |
  |---|---|---|
  | Sin procesar | Validaciones 4 a 6 y descuento | `InsumosDescontados`, o `InsumosRechazados` guardado como `RECHAZADO` |
  | Con descuento guardado (`DESCONTADO`, `RECHAZADO`, o `RESTAURADO` después de descontar) | Ninguno | La misma respuesta de descuento de la primera vez |
  | `RESTAURADO` sin descuento previo | Ninguno | `InsumosRechazados` con `SAGA_COMPENSADA` |

#### Restauración (compensación)

- **RQ-SAG-06**: El servicio debe consumir `RestaurarInsumos` (versión 1) con `datos`: `idSaga`, `idLabor`.
- **RQ-SAG-07**: Efecto según el estado del `idSaga`:

  | Estado del `idSaga` | Efecto | Respuesta |
  |---|---|---|
  | `DESCONTADO` | Una `ENTRADA` por cada `SALIDA` de ese `idSaga`, por la misma cantidad y con su costo unitario, motivo "Compensación de saga {idSaga}"; resultado pasa a `RESTAURADO` | `InsumosRestaurados`, `sinEfecto = false` |
  | Sin procesar | Se guarda `RESTAURADO` sin descuento | `InsumosRestaurados`, `sinEfecto = true` |
  | `RECHAZADO` | Ninguno; conserva `RECHAZADO` | `InsumosRestaurados`, `sinEfecto = true` |
  | Con restauración guardada | Ninguno | La misma respuesta de la primera restauración |

- **RQ-SAG-08**: Las cantidades a restaurar se leen de los movimientos `SALIDA` de ese `idSaga`, nunca del comando (constitución §5). La auditoría usa la acción `RESTAURAR_INSUMOS_SAGA`.

#### Respuestas

- **RQ-SAG-09**: Se publican en la cola `servicio-operaciones.respuestas-saga`, con el mismo `idCorrelacion` del comando y `origen = servicio-inventario`:

  | `tipo` | `datos` |
  |---|---|
  | `InsumosDescontados` | `idSaga`, `idLabor`, `costoTotal`, `items: [{ idInsumo, cantidad, costoUnitario }]` |
  | `InsumosRechazados` | `idSaga`, `idLabor`, `codigo`, `motivo`, `insumosAfectados: [{ idInsumo, cantidadSolicitada, stockDisponible }]` |
  | `InsumosRestaurados` | `idSaga`, `idLabor`, `sinEfecto`, `items: [{ idInsumo, cantidad }]` |

  Decimales como texto (`costoTotal` con 2 decimales, cantidades con 3, costo unitario con 4). En `DATOS_INVALIDOS` sin `idSaga` o `idLabor` válidos, esos campos van como vienen en el comando o `null`.

#### Comunes

- **RQ-SAG-10**: Idempotencia por `idSaga` (colección `sagas_procesadas`), que cubre también la idempotencia por `idMensaje` (README D-16).
- **RQ-SAG-11**: Los comandos de un mismo `idSaga` se procesan de forma serializada (constitución §5).
- **RQ-SAG-12**: Los movimientos, el cambio de stock, el resultado de la Saga y la auditoría se guardan en la misma transacción (constitución §4).
- **RQ-SAG-13**: Los fallos técnicos se reintentan 3 veces con espera creciente y luego van a la DLQ; nunca se publica un rechazo por un fallo técnico (constitución §8).
- **RQ-SAG-14**: Después de publicar la respuesta, se evalúa el stock bajo de los insumos afectados (`spec-stock-bajo.md`).
- **RQ-SAG-15**: Los logs de cada mensaje incluyen `idCorrelacion`, `idMensaje`, `tipo` y resultado.

### Entidades clave

- **MovimientoInventario** con `idSaga` e `idLabor` (`spec-movimientos.md`).
- **SagaProcesada**: `idSaga`, `idLabor`, `resultado` (`DESCONTADO` / `RECHAZADO` / `RESTAURADO`), `descuento` (la respuesta de descuento guardada: `costoTotal` e `items` con cantidad y costo unitario, o `codigo`, `motivo` e `insumosAfectados`), `restauracion` (la respuesta de restauración guardada: `sinEfecto` e `items`), `fechaProcesamiento`, `fechaActualizacion`.
- **ResultadoSagaProcesada**: `DESCONTADO` / `RECHAZADO` / `RESTAURADO` (glosario de la constitución).

## Códigos de rechazo en mensajes

| Código | Cuándo |
|---|---|
| `DATOS_INVALIDOS` | Datos ausentes o fuera de formato, `items` vacío o con insumos repetidos, cantidad no textual o ≤ 0, decimales con `UNIDAD`, `idCorrelacion` ≠ `idSaga`, versión no soportada |
| `INSUMO_NO_ENCONTRADO` | Al menos un insumo no existe |
| `STOCK_INSUFICIENTE` | Al menos un insumo no alcanza (RN-04) |
| `SAGA_COMPENSADA` | El `idSaga` fue restaurado antes de recibir el descuento |

`RestaurarInsumos` no tiene rechazo de negocio: siempre responde `InsumosRestaurados`. Con datos inválidos (sin `idSaga` válido), el mensaje va a la DLQ, porque no hay forma segura de responder.

## Criterios de éxito

- **CE-SAG-01**: Tests obligatorios de la constitución §6 en verde: descuento exitoso, stock insuficiente, insumo inexistente, insumo repetido en `items`, comando duplicado con la misma respuesta aunque cambie el costo unitario, compensación, compensación duplicada, compensación sin descuento previo, descuento tardío después de una compensación y redondeo del costo total.
- **CE-SAG-02**: Test de concurrencia: dos descuentos simultáneos sobre el mismo insumo nunca dejan stock negativo (constitución §6); con 100 entregas del mismo comando en paralelo, el stock se descuenta una sola vez.
- **CE-SAG-03**: Con descuento y restauración del mismo `idSaga` en cualquier orden y en paralelo, el stock final es igual al inicial.
- **CE-SAG-04**: Ningún comando termina sin respuesta ni sin estar en la DLQ.
- **CE-SAG-05**: Cada comando se procesa en menos de 1 s en condiciones normales, para no consumir el tiempo límite del coordinador.

## Supuestos

- El coordinador solo envía `DescontarInsumos` para labores realizadas con insumos (RN-07); este servicio no conoce labores ni campañas.
- El coordinador decide qué hacer con cada respuesta (constitución de operaciones §6); este servicio no conoce el estado de la labor.

## Aclaraciones

- **AC-01** — Resuelta (constitución v2.6.0): `RestaurarInsumos` lleva solo `idSaga` e `idLabor`; las cantidades salen de los movimientos.
- **AC-02** — Resuelta (constitución v2.6.0): descuento tardío tras una compensación → `SAGA_COMPENSADA`.
- **AC-03** — Resuelta (2026-11-02): RQ-SAG-09 es el contrato de las tres respuestas. Cumple el contenido mínimo de la constitución (`costoTotal`, código e insumos afectados) y sigue el estilo de las respuestas de `servicio-gestion`. Como `servicio-operaciones` todavía no tiene specs, su spec de la Saga lo adopta tal cual; un cambio posterior se acuerda entre ambos y sube la `version` del mensaje.

## Fuera de alcance

- Coordinar la Saga, conocer labores o llamar a otros servicios.
- Restauraciones parciales.
- Reprocesar mensajes de la DLQ (se hace a mano desde el panel de RabbitMQ).

---

# 2. Plan

Reutiliza la operación de stock de `spec-movimientos.md`, la conexión a RabbitMQ y el publicador de `spec-stock-bajo.md`. Es el primer consumidor del servicio.

## 2.1 Colas

| Cola | Dueño | Declaración |
|---|---|---|
| `servicio-inventario.comandos` | Este servicio | Durable, `x-dead-letter-exchange: ""`, `x-dead-letter-routing-key: servicio-inventario.comandos.dlq` |
| `servicio-inventario.comandos.dlq` | Este servicio | Durable, sin argumentos |
| `servicio-operaciones.respuestas-saga` | `servicio-operaciones` | Durable, sin argumentos. Este servicio también la declara para no perder respuestas si arranca primero; los argumentos coinciden con los de `servicio-gestion` |

Comandos y respuestas usan el exchange por defecto, con el nombre de la cola como routing key. Las respuestas se publican con `persistent: true` y confirmación del broker.

## 2.2 Consumidor y reintentos

`ComandosSagaConsumidor` (`adapters/inbound/messaging`), un solo consumidor para los dos comandos:

```text
canal con prefetch 10, ack manual
por cada mensaje:
  1. JSON.parse y validación del sobre (idMensaje, idCorrelacion, tipo conocido)
       falla → nack(requeue=false) → DLQ; log de error. Sin reintentos.
  2. intentos = 0
     loop:
       try:
         respuesta, insumosAfectados = casoDeUso[tipo].ejecutar(sobre)   ← transacción propia
         publicador.publicarRespuesta(respuesta)                          ← espera confirmación
         ack
         evaluarStockBajo(insumosAfectados) sin esperar                   ← spec-stock-bajo.md
         break
       catch error técnico:
         intentos++
         si intentos > 3 → nack(requeue=false) → DLQ; log de error; break
         esperar 1 s, 2 s, 4 s según intentos
```

- Reintentos en el proceso (README D-12). Si el proceso se cae mientras espera, el mensaje no confirmado vuelve a la cola y se reprocesa con idempotencia.
- Los rechazos de negocio no son errores: el caso de uso devuelve un `InsumosRechazados` que se publica y confirma.
- `version` distinta de 1 en `DescontarInsumos` → `DATOS_INVALIDOS`. En `RestaurarInsumos` sin `idSaga` válido → DLQ (no hay a quién responder con seguridad).

## 2.3 Serialización por `idSaga` e idempotencia

Cada comando corre dentro de `UnidadTrabajo` y empieza escribiendo en el documento de su `idSaga`:

```text
1. bloqueo = sagas_procesadas.findOneAndUpdate(
       { _id: idSaga },
       { $setOnInsert: { id_labor, fecha_procesamiento: ahora }, $set: { fecha_actualizacion: ahora } },
       { upsert: true, new: true, session })
2. decide según bloqueo.resultado / bloqueo.descuento / bloqueo.restauracion (tablas RQ-SAG-05 y RQ-SAG-07)
3. aplica movimientos (si corresponde) y guarda el resultado en el mismo documento
```

- La escritura del paso 1 hace que dos transacciones del mismo `idSaga` choquen (`WriteConflict`); `withTransaction` reintenta la perdedora, que en el reintento ya ve el resultado de la ganadora. Así se cumple RQ-SAG-11 sin bloqueos explícitos (equivale al bloqueo consultivo de `servicio-gestion`).
- Un documento recién creado en el paso 1 sin `resultado` significa "sin procesar". Si la transacción termina en un rechazo `DATOS_INVALIDOS` del paso 2 de RQ-SAG-02, no se abre transacción.

## 2.4 Modelo de datos

Colección `sagas_procesadas` (`_id` = `idSaga`, sin índices adicionales):

```text
{
  _id: "S1",
  id_labor: "L1",
  resultado: "DESCONTADO" | "RECHAZADO" | "RESTAURADO" | null,
  descuento: {                               // null si nunca se procesó un descuento
    tipo: "InsumosDescontados" | "InsumosRechazados",
    costo_total: Decimal128,                 // solo descontado
    items: [{ id_insumo, cantidad: Decimal128, costo_unitario: Decimal128 }],
    codigo, motivo,                          // solo rechazado
    insumos_afectados: [{ id_insumo, cantidad_solicitada: Decimal128, stock_disponible: Decimal128 | null }]
  },
  restauracion: {                            // null si nunca se procesó una restauración
    sin_efecto: Boolean,
    items: [{ id_insumo, cantidad: Decimal128 }]
  },
  fecha_procesamiento: Date,
  fecha_actualizacion: Date
}
```

- `descuento` y `restauracion` guardan cada respuesta por separado, para repetir la del descuento aunque después se haya restaurado (Historia 3, escenario 5) y con el costo original aunque cambie el costo unitario (Historia 2, escenario 2).
- `SAGA_COMPENSADA` no se guarda en `descuento`: es una respuesta determinística del estado `RESTAURADO` sin descuento.

## 2.5 Casos de uso

**`DescontarInsumosCasoUso`** (`application/use-cases/descontar-insumos.caso-uso.ts`):

1. Valida el formato (RQ-SAG-02 paso 2) con una función pura del dominio; si falla, devuelve `DATOS_INVALIDOS` sin transacción.
2. Dentro de `UnidadTrabajo`: bloqueo y decisión (2.3).
3. Si corresponde procesar: lee todos los insumos; arma la lista de faltantes, de cantidades no enteras con `UNIDAD` y de insuficientes, en ese orden de prioridad; si alguna no está vacía, guarda `RECHAZADO` y devuelve el rechazo.
4. Si todo alcanza: por cada ítem, `RegistrarMovimientoCasoUso.registrarDentroDeTransaccion` (`SALIDA`); si `aplicarMovimiento` devuelve `null` (carrera perdida con otra operación fuera de la transacción), lanza un error transitorio para que `withTransaction` reintente y la nueva lectura decida.
5. Calcula `costoTotal` con `Dinero` (suma exacta y `redondearA2()`), guarda `DESCONTADO` con `descuento` y devuelve la respuesta y los insumos afectados.

**`RestaurarInsumosCasoUso`** (`application/use-cases/restaurar-insumos.caso-uso.ts`):

1. Dentro de `UnidadTrabajo`: bloqueo y decisión (tabla RQ-SAG-07).
2. Si es `DESCONTADO`: `repositorioMovimiento.listarPorSaga(idSaga, SALIDA)` (método nuevo del puerto, que se agrega aquí); por cada salida, una `ENTRADA` por la misma cantidad y con el costo unitario de la salida; guarda `RESTAURADO` con `restauracion`.
3. Devuelve la respuesta y los insumos afectados.

`MovimientoInventario.registrar` acepta un `costoUnitario` explícito para las entradas de compensación; si no se pasa, copia el del insumo (`spec-movimientos.md`).

## 2.6 Diseño por capas

| Capa | Archivo | Responsabilidad |
|---|---|---|
| `domain/saga` | `saga-procesada.entidad.ts`, `resultado-saga-procesada.enum.ts` | Estado del `idSaga` y decisión de las tablas RQ-SAG-05 y RQ-SAG-07 |
| `domain/saga` | `validacion-comando-descuento.ts` | Validación pura del formato de `datos` |
| `application/ports` | `repositorio-saga-procesada.puerto.ts`; se amplía `repositorio-movimiento.puerto.ts` con `listarPorSaga` | Puertos |
| `application/use-cases` | `respuestas-saga.ts` | `datos` de RQ-SAG-09 (decimales como texto), `ResultadoComandoSaga` (respuesta, insumos afectados y advertencia para el log) y `ComandoNoProcesable` (a la DLQ sin reintentos) |
| `application/use-cases` | `descontar-insumos.caso-uso.ts`, `restaurar-insumos.caso-uso.ts` | 2.5 |
| `adapters/outbound/persistence` | `saga-procesada.esquema.ts`, mapper, `repositorio-saga-procesada.mongo.ts` | 2.3 y 2.4 |
| `adapters/inbound/messaging` | `comandos-saga.consumidor.ts`, `sobre-mensaje.ts`, `topologia-saga.ts` | 2.2, declaración de colas (2.1) y publicación de la respuesta |

La constitución separa `descontar-insumos` y `restaurar-insumos` como casos de uso; un solo consumidor los despacha por `tipo` porque comparten cola.

Ajustes respecto del plan original:

- La respuesta la publica el propio consumidor, en su canal con confirmaciones, y no un puerto de `application`: es la respuesta del comando, como el cuerpo de una respuesta HTTP. Por eso `PublicadorEventos` no se amplía y `topologia-saga.ts` vive junto al consumidor.
- `004-crear-coleccion-sagas.ts` crea `sagas_procesadas` por adelantado, para que el primer `upsert` no la cree dentro de una transacción con otros comandos simultáneos.
- Si `aplicarMovimiento` devuelve `null` (una carrera que la transacción no detectó), el `STOCK_INSUFICIENTE` aborta la transacción y el consumidor lo trata como fallo técnico: reintenta el comando y la nueva lectura decide.
- `RestaurarInsumos` con versión distinta de 1, `idSaga` o `idLabor` que no son UUID, o `idCorrelacion` distinto de `idSaga`, va a la DLQ (`ComandoNoProcesable`): no tiene un rechazo de negocio.
- `insumos_afectados` guarda las cantidades como texto, porque en un `DATOS_INVALIDOS` pueden no ser decimales válidos.
- `RegistrarMovimientoCasoUso.registrarDentroDeTransaccion` recibe la acción de auditoría (`DESCONTAR_INSUMOS_SAGA` o `RESTAURAR_INSUMOS_SAGA`).

## 2.7 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `saga-procesada.entidad.spec.ts` | Cada fila de las tablas RQ-SAG-05 y RQ-SAG-07 |
| Unitario | `validacion-comando-descuento.spec.ts` | `items` vacío, repetido, cantidad número JSON, ≤ 0, más de 3 decimales, `idCorrelacion` ≠ `idSaga`, versión |
| Unitario | `saga.caso-uso.spec.ts` | Descuento y restauración con dobles: prioridad de rechazos, cálculo y redondeo de `costoTotal` (`0.3705 → 0.37`, suma de varios ítems antes de redondear), advertencias, `ComandoNoProcesable` |
| Integración | `descontar-insumos.int-spec.ts` | Historia 1 completa con RabbitMQ y MongoDB reales |
| Integración | `idempotencia-saga.int-spec.ts` | Historia 2, incluido el costo unitario cambiado y 100 entregas en paralelo (CE-SAG-02) |
| Integración | `restaurar-insumos.int-spec.ts` | Historia 3 completa; descuento y restauración en paralelo y en ambos órdenes (CE-SAG-03) |
| Integración | `fallos-saga.int-spec.ts` | Historia 4: repositorio que falla → 4 intentos y DLQ sin respuesta; sobre inválido y tipo desconocido → DLQ sin reintentos; datos inválidos → `DATOS_INVALIDOS` |
| Integración | `concurrencia-saga.int-spec.ts` | Dos Sagas sobre el mismo insumo con stock para una; Saga y salida manual simultáneas; nunca stock negativo (CE-SAG-02) |

Los tests publican en `servicio-inventario.comandos` y leen de `servicio-operaciones.respuestas-saga` y de la DLQ con `ClienteSaga`, que hace de coordinador y declara las tres colas con los mismos argumentos que el servicio (si no coincidieran, RabbitMQ rechazaría la declaración). Para no esperar 7 s por test, la espera entre reintentos (`ESPERAS_REINTENTO_SAGA`) vale 10 ms, 20 ms y 40 ms en los tests.

---

# 3. Tareas

- [x] **T01** — Declarar las colas de 2.1 (`topologia-saga.ts`) y ampliar el publicador con `publicarRespuesta`. *Hecho cuando:* un test de integración verifica las tres colas y sus argumentos. `ClienteSaga` las declara con los mismos argumentos en cada archivo de la Saga; además se verificó en Docker Compose (`rabbitmqctl list_queues`).
- [x] **T02** — Crear `SagaProcesada`, `ResultadoSagaProcesada` y `validacion-comando-descuento.ts`, con sus tests unitarios.
- [x] **T03** — Crear el esquema, el mapper y `RepositorioSagaProcesadaMongo`, con el bloqueo de 2.3.
- [x] **T04** — Implementar `ComandosSagaConsumidor` con reintentos y DLQ (2.2).
- [x] **T05** — Implementar `DescontarInsumosCasoUso`. *Hecho cuando:* pasan `descontar-insumos.caso-uso.spec.ts` y `descontar-insumos.int-spec.ts` (salvo el escenario 7).
- [x] **T06** — Implementar `RestaurarInsumosCasoUso`. *Hecho cuando:* pasan `restaurar-insumos.int-spec.ts` y el escenario 7 de la Historia 1.
- [x] **T07** — Escribir `idempotencia-saga.int-spec.ts`, `fallos-saga.int-spec.ts` y `concurrencia-saga.int-spec.ts`.
- [x] **T08** — Conectar la evaluación de stock bajo después de cada respuesta (RQ-SAG-14) y completar el escenario 4 de la Historia 3 de `spec-movimientos.md` (actor de la Saga en el listado).
- [ ] **T09** — Cuando exista la spec de la Saga de `servicio-operaciones`, verificar que consume el contrato de RQ-SAG-09 (AC-03) y las colas de 2.1 sin cambios. Pendiente: `servicio-operaciones` todavía no tiene specs.
- [x] **T10** — Verificación final: `npm test` en verde, cobertura ≥ 80 % y criterios CE-SAG-01 a CE-SAG-05 cubiertos.
