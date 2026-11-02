# Registro y anulación de costo desde la Saga — `servicio-gestion`

| Campo | Valor |
|---|---|
| Servicio | `servicio-gestion` |
| Archivo | `specs/spec-costo-saga.md` |
| Estado | Spec aprobada (2026-11-01) · Plan y tareas en borrador |
| Fecha | 2026-11-01 |
| Constitución | v2.4.0 (secciones 4, 5, 6 y 8) |
| Trazabilidad | CU-04 (actor Sistema) y CU-12 (participante) · RF-04, RF-13 · RN-06, RN-08, RN-09 · RNF-10, RNF-11, RNF-22 |
| Depende de | `spec-campanias.md`, `spec-costos-manuales.md` (entidad `CostoCampania`) |


Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Contexto

Cuando un técnico registra una labor con insumos, `servicio-operaciones` (coordinador) ejecuta la Saga: primero `servicio-inventario` descuenta los insumos y calcula su costo; después este servicio registra ese costo en la campaña. Este servicio es **participante**: recibe comandos, responde con un resultado y no llama a nadie más.

Si el coordinador no recibe respuesta a tiempo, no sabe si el costo se registró o si el comando sigue en la cola. Por eso envía primero la compensación `AnularCostoCampania` a este servicio, y solo envía `RestaurarInsumos` a `servicio-inventario` después de recibir `CostoCampaniaAnulado`.

```text
servicio-operaciones ──RegistrarCostoCampania──▶ servicio-gestion
servicio-operaciones ◀──CostoCampaniaRegistrado / CostoCampaniaRechazado──

(tiempo límite agotado)
servicio-operaciones ──AnularCostoCampania──▶ servicio-gestion
servicio-operaciones ◀──CostoCampaniaAnulado / AnulacionCostoRechazada──
```

## Escenarios de usuario y pruebas

### Historia 1 — Registrar el costo de insumos de una labor (Prioridad: P1)

Como sistema coordinador de la Saga, quiero que el costo de los insumos descontados quede registrado en la campaña, para que la labor quede `CONFIRMADA` y los indicadores reflejen el gasto real.

**Por qué esta prioridad:** es el paso que cierra la Saga; sin él, ninguna labor con insumos se confirma.

**Prueba independiente:** se publica el comando en la cola del servicio (Testcontainers con RabbitMQ) y se verifica el costo guardado y la respuesta publicada.

**Escenarios de aceptación:**

1. **Dado** una campaña `EN_CURSO`, **cuando** llega `RegistrarCostoCampania` con `idSaga` S1, `idLabor` L1 y `monto` `"820.50"`, **entonces** se registra un costo de Bs 820,50, categoría `INSUMO`, origen `SAGA`, con `idSaga` S1 e `idLabor` L1, y se publica `CostoCampaniaRegistrado` con `idCorrelacion` = S1.
2. **Dado** una campaña `PLANIFICADA`, **cuando** llega el comando, **entonces** el costo se registra igual que en el escenario 1.
3. **Dado** una campaña `FINALIZADA`, **cuando** llega el comando, **entonces** no se registra nada y se publica `CostoCampaniaRechazado` con código `CAMPANIA_FINALIZADA` (RN-06).
4. **Dado** un `idCampania` inexistente, **cuando** llega el comando, **entonces** se publica `CostoCampaniaRechazado` con código `CAMPANIA_NO_ENCONTRADA`.
5. **Dado** que S1 ya fue anulado (Historia 4), **cuando** llega `RegistrarCostoCampania` con `idSaga` S1, **entonces** no se registra nada y se publica `CostoCampaniaRechazado` con código `SAGA_ANULADA`.

---

### Historia 2 — Procesar mensajes duplicados sin duplicar costos (Prioridad: P1)

Como sistema coordinador, quiero poder reenviar el comando (por reintento o recuperación tras un reinicio) sin que el costo se duplique, para que la Saga sea segura ante fallos (RN-09).

**Por qué esta prioridad:** RabbitMQ entrega "al menos una vez" y el coordinador reintenta; sin idempotencia los costos se inflarían.

**Prueba independiente:** se envía el mismo comando varias veces y se verifica un único costo y respuestas iguales.

**Escenarios de aceptación:**

1. **Dado** que S1 ya se registró, **cuando** llega otra vez un comando con `idSaga` S1 (mismo o distinto `idMensaje`), **entonces** no se crea un segundo costo y se publica de nuevo `CostoCampaniaRegistrado` con los mismos datos de la primera vez.
2. **Dado** que S2 fue rechazado por `CAMPANIA_FINALIZADA`, **cuando** llega otra vez con `idSaga` S2, **entonces** se publica de nuevo el mismo `CostoCampaniaRechazado`, aunque el estado de la campaña haya cambiado.
3. **Dado** que S1 ya se procesó, **cuando** llega un comando con `idSaga` S1 pero con otro monto o campaña, **entonces** se responde el resultado original y se registra una advertencia en el log con el `idCorrelacion`.
4. **Dado** dos copias del mismo comando procesadas en paralelo, **entonces** solo existe un costo con `idSaga` S1 (restricción `UNIQUE`), y ambas copias producen la misma respuesta.

---

### Historia 3 — Manejar fallos técnicos sin perder mensajes (Prioridad: P1)

Como operador del sistema, quiero que un fallo técnico (base de datos caída, error inesperado) no pierda el comando ni genere una respuesta falsa, para poder diagnosticar y reprocesar (RNF-11).

**Por qué esta prioridad:** la constitución prohíbe descartar mensajes en silencio.

**Prueba independiente:** se simula la caída de PostgreSQL durante el consumo y se verifican reintentos y paso a la Dead Letter Queue.

**Escenarios de aceptación:**

1. **Dado** que la base de datos no responde, **cuando** llega un comando, **entonces** no se publica respuesta, el mensaje se reintenta 3 veces con espera creciente y, si sigue fallando, va a la Dead Letter Queue.
2. **Dado** un mensaje cuyo sobre no se puede interpretar (JSON inválido o sin `idCorrelacion`), **entonces** va a la Dead Letter Queue sin reintentos, con log de error.
3. **Dado** un sobre válido con `datos` inválidos (monto 0, monto como número JSON, categoría distinta de `INSUMO`, campos ausentes), **entonces** se publica la respuesta de rechazo con código `DATOS_INVALIDOS` (es un rechazo de negocio, no un fallo técnico).

---

### Historia 4 — Anular el costo cuando el coordinador compensa (Prioridad: P1)

Como sistema coordinador, quiero anular el costo de una Saga cuyo resultado desconozco, para que no quede en la campaña el costo de insumos que se van a devolver al inventario.

**Por qué esta prioridad:** sin anulación, un comando que llega tarde (por ejemplo, tras una caída de este servicio) registra un costo inexistente y altera los indicadores.

**Prueba independiente:** se publica `AnularCostoCampania` antes y después de `RegistrarCostoCampania`, y con la campaña en cada estado, verificando el costo, el resultado guardado y la respuesta.

**Escenarios de aceptación:**

1. **Dado** que S1 tiene un costo registrado en una campaña `EN_CURSO`, **cuando** llega `AnularCostoCampania` con `idSaga` S1, **entonces** el costo queda anulado (deja de sumar en totales e indicadores), S1 queda con resultado `ANULADO` y se publica `CostoCampaniaAnulado` con el `idCosto` y `sinEfecto = false`.
2. **Dado** que S3 nunca se registró, **cuando** llega `AnularCostoCampania` con `idSaga` S3, **entonces** se publica `CostoCampaniaAnulado` con `sinEfecto = true` y S3 queda con resultado `ANULADO`; un `RegistrarCostoCampania` posterior con S3 se rechaza con `SAGA_ANULADA`.
3. **Dado** que S1 tiene un costo registrado y la campaña ya está `FINALIZADA`, **cuando** llega `AnularCostoCampania`, **entonces** el costo se conserva, S1 sigue `REGISTRADO` y se publica `AnulacionCostoRechazada` con código `CAMPANIA_FINALIZADA`.
4. **Dado** que S2 fue rechazado, **cuando** llega `AnularCostoCampania` con S2, **entonces** se publica `CostoCampaniaAnulado` con `sinEfecto = true` y S2 conserva su resultado `RECHAZADO`.
5. **Dado** que S1 ya fue anulado, **cuando** llega otra vez `AnularCostoCampania` con S1, **entonces** se publica la misma respuesta de la primera vez sin efectos nuevos (RN-09).

---

### Casos borde

- El comando de registro llega mientras un administrador finaliza la campaña: o el costo queda registrado antes de la finalización, o se rechaza con `CAMPANIA_FINALIZADA`. Nunca ambas cosas.
- El registro y la anulación del mismo `idSaga` llegan en paralelo: se procesan uno después del otro (bloqueo por `idSaga`); el resultado final es siempre `ANULADO` y el costo, si llegó a crearse, queda anulado.
- `version` del mensaje distinta de 1: se rechaza con `DATOS_INVALIDOS` hasta que exista una versión nueva acordada.
- Falla la publicación de la respuesta después de guardar el cambio: el mensaje se reintenta; por idempotencia no hay efectos nuevos y la respuesta se publica en el reintento.
- Dos Sagas distintas registran costos en la misma campaña al mismo tiempo: una puede fallar por `@Version`. Es un fallo técnico: se reintenta y, si se agotan los reintentos, va a la Dead Letter Queue sin respuesta, y el coordinador compensa por tiempo límite.
- Anulación con `idCampania` distinto del que tiene el costo registrado para ese `idSaga`: se anula el costo de ese `idSaga` (manda el `idSaga`) y se registra una advertencia en el log.

## Requisitos

### Requisitos funcionales

#### Registro

- **RQ-SAG-01**: El servicio debe consumir el comando `RegistrarCostoCampania` (versión 1) de su cola, con el sobre común de mensajería y `datos`:

  ```json
  {
    "idSaga": "uuid",
    "idLabor": "uuid",
    "idCampania": "uuid",
    "monto": "820.50",
    "categoria": "INSUMO"
  }
  ```

  `monto` es texto decimal, según la convención común de la constitución v2.1.0.
- **RQ-SAG-02**: Validaciones, en este orden:
  1. Sobre interpretable con `idMensaje` e `idCorrelacion`; si no, Dead Letter Queue.
  2. `datos` completos, `monto` como texto decimal > 0 con hasta 12 dígitos enteros y 2 decimales, `categoria = INSUMO`, `idCorrelacion = idSaga`; si no, rechazo `DATOS_INVALIDOS`.
  3. Si el `idSaga` ya tiene resultado guardado: `REGISTRADO` o `RECHAZADO` → se repite la respuesta original; `ANULADO` → rechazo `SAGA_ANULADA`.
  4. La campaña existe; si no, rechazo `CAMPANIA_NO_ENCONTRADA`.
  5. La campaña no está `FINALIZADA`; si lo está, rechazo `CAMPANIA_FINALIZADA` (RN-06).
- **RQ-SAG-03**: Si pasa las validaciones, se registra un `CostoCampania` con `categoria = INSUMO`, `origen = SAGA`, `monto`, `idSaga`, `idLabor`, `fecha` = fecha UTC de `fechaOcurrencia` y `descripcion` = "Insumos de la labor {idLabor}".
- **RQ-SAG-04**: Respuestas, con el mismo `idCorrelacion` (= `idSaga`):
  - `CostoCampaniaRegistrado` con `datos`: `idSaga`, `idLabor`, `idCampania`, `idCosto`, `monto`.
  - `CostoCampaniaRechazado` con `datos`: `idSaga`, `idLabor`, `idCampania`, `codigo`, `motivo`.

#### Anulación (compensación)

- **RQ-SAG-05**: El servicio debe consumir el comando `AnularCostoCampania` (versión 1) con `datos`: `idSaga`, `idLabor`, `idCampania`.
- **RQ-SAG-06**: Efecto según el estado del `idSaga`:

  | Estado del `idSaga` | Campaña | Efecto | Respuesta |
  |---|---|---|---|
  | `REGISTRADO` | No finalizada | El costo queda anulado; resultado pasa a `ANULADO` | `CostoCampaniaAnulado`, `sinEfecto = false` |
  | `REGISTRADO` | `FINALIZADA` | Ninguno; el costo se conserva | `AnulacionCostoRechazada`, código `CAMPANIA_FINALIZADA` |
  | Sin procesar | Cualquiera | Se guarda resultado `ANULADO` | `CostoCampaniaAnulado`, `sinEfecto = true` |
  | `RECHAZADO` | Cualquiera | Ninguno | `CostoCampaniaAnulado`, `sinEfecto = true` |
  | `ANULADO` | Cualquiera | Ninguno | La misma respuesta de la primera anulación |

- **RQ-SAG-07**: Un costo anulado no se borra: queda con `anulado = true` y `fechaAnulacion`, no se lista ni suma en totales e indicadores (`spec-costos-manuales.md` y `spec-indicadores.md`), y conserva su `idSaga` para la idempotencia.
- **RQ-SAG-08**: Respuestas de la anulación, con el mismo `idCorrelacion`:
  - `CostoCampaniaAnulado` con `datos`: `idSaga`, `idLabor`, `idCampania`, `idCosto` (o `null`), `sinEfecto`.
  - `AnulacionCostoRechazada` con `datos`: `idSaga`, `idLabor`, `idCampania`, `idCosto`, `codigo`, `motivo`.

#### Comunes a ambos comandos

- **RQ-SAG-09**: Las respuestas se publican en la cola del coordinador (`servicio-operaciones`), según la sección 5 de la constitución. El nombre de la cola se acuerda en el plan con `servicio-operaciones`.
- **RQ-SAG-10**: Idempotencia por `idSaga` (resultado guardado en `SagaProcesada`) y por `idMensaje` (regla común).
- **RQ-SAG-11**: Los comandos de un mismo `idSaga` se procesan de forma serializada (bloqueo por `idSaga`), para que registro y anulación concurrentes no dejen estados intermedios.
- **RQ-SAG-12**: El cambio en el costo, el resultado de `SagaProcesada` y el registro de auditoría se guardan en la misma transacción.
- **RQ-SAG-13**: La columna `idSaga` de los costos tiene restricción `UNIQUE`.
- **RQ-SAG-14**: Los fallos técnicos se reintentan 3 veces con espera creciente y luego van a la Dead Letter Queue; nunca se publica un rechazo por un fallo técnico.
- **RQ-SAG-15**: La auditoría registra como actor la cuenta de servicio o el `origen` del mensaje, con la acción "registrar costo saga" o "anular costo saga".
- **RQ-SAG-16**: Los logs de cada mensaje incluyen `idCorrelacion`, `idMensaje`, `tipo` y resultado.

### Entidades clave

- **CostoCampania** con `origen = SAGA` (definida en `spec-costos-manuales.md`), con `anulado` y `fechaAnulacion`.
- **SagaProcesada**: `idSaga`, `resultado` (`REGISTRADO` / `RECHAZADO` / `ANULADO`), `idCosto` (si se registró), `codigo` y `motivo` (si se rechazó), `respuestaAnulacion` (si se anuló o se intentó anular), `fechaProcesamiento`, `fechaActualizacion`.
- **MensajeProcesado**: `idMensaje`, `fechaProcesamiento` (idempotencia por mensaje).
- **ResultadoSagaProcesada**: `REGISTRADO` / `RECHAZADO` / `ANULADO` (glosario de la constitución v2.1.0).

## Códigos de rechazo en mensajes

| Código | Mensaje | Cuándo |
|---|---|---|
| `DATOS_INVALIDOS` | `CostoCampaniaRechazado` | Datos ausentes o fuera de rango, monto no textual, categoría distinta de `INSUMO`, versión no soportada |
| `CAMPANIA_NO_ENCONTRADA` | `CostoCampaniaRechazado` | La campaña no existe |
| `CAMPANIA_FINALIZADA` | `CostoCampaniaRechazado` | La campaña está finalizada (RN-06) |
| `SAGA_ANULADA` | `CostoCampaniaRechazado` | El `idSaga` ya fue anulado |
| `DATOS_INVALIDOS` | `AnulacionCostoRechazada` | Datos ausentes o versión no soportada |
| `CAMPANIA_FINALIZADA` | `AnulacionCostoRechazada` | El costo está registrado en una campaña ya finalizada |

## Criterios de éxito

- **CE-SAG-01**: Tests obligatorios de la sección 6 de la constitución en verde: éxito, rechazo, mensaje duplicado, anulación, anulación duplicada, anulación sin registro previo, anulación rechazada por campaña finalizada y registro tardío después de una anulación; más fallo técnico con paso a la Dead Letter Queue.
- **CE-SAG-02**: Con 100 entregas del mismo comando (en serie y en paralelo) existe exactamente un costo con ese `idSaga`.
- **CE-SAG-03**: Con registro y anulación del mismo `idSaga` enviados en cualquier orden y en paralelo, el resultado final es siempre `ANULADO` y ningún costo de esa Saga suma en la campaña (salvo campaña ya finalizada).
- **CE-SAG-04**: Ningún comando termina sin respuesta ni sin estar en la Dead Letter Queue.
- **CE-SAG-05**: Cada comando se procesa en menos de 1 s en condiciones normales, para no consumir el tiempo límite del coordinador.

## Supuestos

- El monto recibido es el costo total calculado por `servicio-inventario`, redondeado a 2 decimales; este servicio no lo recalcula. Con costo `0.00`, el coordinador no envía el comando (constituciones de inventario v2.4.0 y operaciones v2.5.0).
- El monto está en bolivianos (`BOB`, README D-01).
- Una `AnulacionCostoRechazada` deja la labor `PENDIENTE_REVISION` en `servicio-operaciones`, sin restaurar insumos, para que la resuelva el administrador (constitución de operaciones v2.5.0, sección 6).

## Aclaraciones

- **AC-01** — Resuelta (2026-11-01, constitución v2.1.0): se agrega la compensación `AnularCostoCampania` y el rechazo `SAGA_ANULADA` (Historia 4).
- **AC-02** — Resuelta (2026-11-01, constitución v2.1.0, convención común): `monto` viaja como texto decimal (`"820.50"`).

## Fuera de alcance

- Coordinar la Saga o llamar a otros servicios (rol de `servicio-operaciones`).
- Recalcular el costo de los insumos.
- Costos de categorías distintas de `INSUMO` por la Saga.
- Anular costos de campañas ya finalizadas (se resuelve manualmente desde la labor en revisión).


---

# 2. Plan

Reutiliza la base del servicio (Fase 0 de `spec-parcelas.md`), el agregado `Campania` y la tabla `costo_campania` de `spec-costos-manuales.md`. Es la primera funcionalidad con mensajería. Criterio: lo mínimo que cumple la spec.

## 2.1 Dependencias y configuración

- Se agregan `spring-boot-starter-amqp` y, para tests, el módulo `rabbitmq` de Testcontainers (`rabbitmq:4-management-alpine`, la misma versión de Docker Compose, con `@ServiceConnection` en `PruebaIntegracionBase`).
- Variables de entorno, que Spring Boot lee directamente: `SPRING_RABBITMQ_HOST`, `SPRING_RABBITMQ_PORT`, `SPRING_RABBITMQ_USERNAME`, `SPRING_RABBITMQ_PASSWORD` y `SPRING_RABBITMQ_SSL_ENABLED` (`true` en producción, para AMQPS).
- `/salud/readiness` pasa a incluir RabbitMQ.

## 2.2 Colas

| Cola | Dueño | Uso |
|---|---|---|
| `servicio-gestion.comandos` | Este servicio | Recibe `RegistrarCostoCampania` y `AnularCostoCampania`. Durable, con dead-letter hacia la cola siguiente |
| `servicio-gestion.comandos.dlq` | Este servicio | Mensajes que fallaron tras los reintentos o que no se pudieron interpretar |
| `servicio-operaciones.respuestas-saga` | `servicio-operaciones` | Recibe las cuatro respuestas. Este servicio también la declara (durable, mismos argumentos) para no perder respuestas si arranca primero |

Los comandos y las respuestas se publican en el exchange por defecto, con el nombre de la cola como routing key.

**Reintentos:** reintentos de Spring AMQP con `max-attempts: 4` (1 intento + 3 reintentos), espera inicial 1 s, multiplicador 2, y `default-requeue-rejected: false`. Agotados, el mensaje pasa a la DLQ.

**Sobre no interpretable:** el consumidor recibe el mensaje crudo. Si el JSON es inválido o falta `idMensaje` o `idCorrelacion`, lo publica directamente en la DLQ, registra el error y lo confirma. Así no se reintenta (Historia 3, escenario 2).

## 2.3 Contrato de mensajes

Todos usan el sobre común (`idMensaje`, `idCorrelacion` = `idSaga`, `tipo`, `version` = 1, `fechaOcurrencia`, `origen`, `datos`). Los montos van como texto.

| `tipo` | Dirección | `datos` |
|---|---|---|
| `RegistrarCostoCampania` | Entrada | `idSaga`, `idLabor`, `idCampania`, `monto`, `categoria` (`INSUMO`) |
| `AnularCostoCampania` | Entrada | `idSaga`, `idLabor`, `idCampania` |
| `CostoCampaniaRegistrado` | Salida | `idSaga`, `idLabor`, `idCampania`, `idCosto`, `monto` |
| `CostoCampaniaRechazado` | Salida | `idSaga`, `idLabor`, `idCampania`, `codigo`, `motivo` |
| `CostoCampaniaAnulado` | Salida | `idSaga`, `idLabor`, `idCampania`, `idCosto` (o `null`), `sinEfecto` |
| `AnulacionCostoRechazada` | Salida | `idSaga`, `idLabor`, `idCampania`, `idCosto`, `codigo`, `motivo` |

Las respuestas llevan `origen` = `servicio-gestion` y el mismo `idCorrelacion` que el comando.

## 2.4 Modelo de datos

**`V7__crear_tablas_saga.sql`**

```sql
CREATE TABLE saga_procesada (
    id_saga               UUID PRIMARY KEY,
    resultado             VARCHAR(20)  NOT NULL CHECK (resultado IN ('REGISTRADO','RECHAZADO','ANULADO')),
    id_campania           UUID,
    id_labor              UUID,
    id_costo              UUID,
    monto                 NUMERIC(14,2),
    codigo                VARCHAR(50),
    motivo                VARCHAR(300),
    anulacion_resultado   VARCHAR(20)  CHECK (anulacion_resultado IN ('ANULADO','RECHAZADA')),
    anulacion_sin_efecto  BOOLEAN,
    anulacion_codigo      VARCHAR(50),
    fecha_procesamiento   TIMESTAMPTZ  NOT NULL,
    fecha_actualizacion   TIMESTAMPTZ  NOT NULL
);

CREATE TABLE mensaje_procesado (
    id_mensaje           UUID PRIMARY KEY,
    id_saga              UUID        NOT NULL,
    fecha_procesamiento  TIMESTAMPTZ NOT NULL
);
```

- Las columnas `anulacion_*` guardan la respuesta de la primera anulación, para repetirla igual ante duplicados.
- `monto` permite repetir `CostoCampaniaRegistrado` con los mismos datos, aunque el comando repetido traiga otro monto.

## 2.5 Flujo de procesamiento

```text
ConsumidorComandosSaga (interfaces/messaging)
  1. Interpreta el sobre; si falla → DLQ directa.
  2. Llama al caso de uso según "tipo" (transacción):
       a. pg_advisory_xact_lock(hashtext(idSaga))  → serializa los comandos del mismo idSaga
       b. Si idMensaje ya existe en mensaje_procesado → repite la respuesta guardada
       c. Aplica las reglas de RQ-SAG-02 o la tabla de RQ-SAG-06
       d. Guarda costo / saga_procesada / mensaje_procesado / auditoría (misma transacción)
  3. Tras el commit, publica la respuesta.
     Si la publicación falla, el mensaje se reintenta; por idempotencia solo se vuelve a publicar.
```

- El bloqueo consultivo de PostgreSQL es una sola consulta nativa y cumple RQ-SAG-11 sin tablas de bloqueo.
- Los rechazos de negocio (`DATOS_INVALIDOS`, `CAMPANIA_NO_ENCONTRADA`, `CAMPANIA_FINALIZADA`, `SAGA_ANULADA`) se responden y confirman. Los fallos técnicos lanzan excepción y siguen el camino de reintentos y DLQ, sin publicar respuesta.
- La auditoría usa `registrarServicio` con el `origen` del mensaje como actor y las acciones `REGISTRAR_COSTO_SAGA` y `ANULAR_COSTO_SAGA`.

## 2.6 Diseño por capas

| Capa | Clase | Responsabilidad |
|---|---|---|
| `domain/campaign` | `Campania` (se amplía) | `registrarCostoSaga(idSaga, idLabor, monto, fecha)` y `anularCostoSaga(idSaga, ahora)`: rechazan si está `FINALIZADA`; actualizan `fechaActualizacion` |
| `domain/saga` | `SagaProcesada`, `ResultadoSagaProcesada`, `RepositorioSagaProcesada` | Resultado guardado por `idSaga` y su puerto |
| `application/campaign` | `RegistrarCostoSagaCasoUso`, `AnularCostoSagaCasoUso` | Pasos 2a a 2d; devuelven la respuesta a publicar |
| `application/port` | `PublicadorMensajes` | Puerto para publicar respuestas |
| `infrastructure/messaging` | `ConfiguracionRabbit`, `PublicadorMensajesRabbit` | Declaración de colas y DLQ; publicación con `RabbitTemplate` y conversor JSON |
| `infrastructure/persistence` | `SagaProcesadaEntidad`, `MensajeProcesadoEntidad` y sus repositorios | Persistencia; consulta nativa del bloqueo consultivo |
| `interfaces/messaging` | `ConsumidorComandosSaga`, `SobreMensaje` | Un solo listener sobre la cola de comandos que despacha por `tipo` |

Un solo consumidor para ambos comandos, porque comparten cola; la constitución da los nombres de archivo solo como referencia.

## 2.7 Tests

| Tipo | Clase | Qué verifica |
|---|---|---|
| Unitario | `CampaniaCostoSagaTest` | Registro y anulación en el agregado, rechazo en campaña finalizada, totales sin anulados |
| Unitario | `AnularCostoSagaCasoUsoTest` | Cada fila de la tabla de RQ-SAG-06 |
| Integración | `RegistrarCostoSagaIT` | Historia 1 completa: éxito en `PLANIFICADA` y `EN_CURSO`, rechazos por finalizada, inexistente y `SAGA_ANULADA` |
| Integración | `IdempotenciaSagaIT` | Historia 2: mismo `idSaga` con distinto `idMensaje`, rechazos repetidos, datos distintos, 100 entregas en paralelo → un solo costo (CE-SAG-02) |
| Integración | `FallosSagaIT` | Historia 3: fallo técnico simulado en el repositorio (detener el PostgreSQL compartido rompería los demás tests) → 4 intentos y DLQ sin respuesta; sobre inválido → DLQ sin reintentos; datos inválidos → `DATOS_INVALIDOS` |
| Integración | `AnularCostoSagaIT` | Historia 4 completa; registro y anulación en paralelo y en ambos órdenes → resultado `ANULADO` (CE-SAG-03) |
| Integración | `FinalizacionConcurrenteSagaIT` | Finalización y costo de la Saga simultáneos → nunca un costo en campaña finalizada (CE-CAM-02 de `spec-campanias.md`) |

Los tests publican en la cola real de RabbitMQ (Testcontainers) y leen las respuestas de `servicio-operaciones.respuestas-saga`.

# 3. Tareas

- [x] **T01** — Agregar Spring AMQP, la configuración de RabbitMQ, RabbitMQ en `PruebaIntegracionBase` y en `/salud/readiness`.
- [x] **T02** — Crear `V7__crear_tablas_saga.sql`, `SagaProcesada` y la persistencia, incluido el bloqueo consultivo.
- [x] **T03** — Ampliar `Campania` con registro y anulación de costos de la Saga, con `CampaniaCostoSagaTest`.
- [x] **T04** — Implementar `ConfiguracionRabbit` (colas, DLQ, reintentos) y `PublicadorMensajesRabbit`.
- [x] **T05** — Implementar `ConsumidorComandosSaga` y `RegistrarCostoSagaCasoUso`. *Hecho cuando:* pasan `RegistrarCostoSagaIT` y `IdempotenciaSagaIT`.
- [x] **T06** — Implementar `AnularCostoSagaCasoUso`. *Hecho cuando:* pasan `AnularCostoSagaCasoUsoTest` y `AnularCostoSagaIT`.
- [x] **T07** — Escribir `FallosSagaIT` y `FinalizacionConcurrenteSagaIT`.
- [x] **T08** — Documentar el contrato de mensajes y las colas para el equipo de `servicio-operaciones` (sección 2.2 y 2.3 de este archivo).
- [x] **T09** — Verificación final: `mvn verify` en verde y criterios CE-SAG-01 a CE-SAG-05 cubiertos.
