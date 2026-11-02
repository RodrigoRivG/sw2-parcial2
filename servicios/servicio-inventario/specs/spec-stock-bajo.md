# Evento de stock bajo — `servicio-inventario`

| Campo | Valor |
|---|---|
| Servicio | `servicio-inventario` |
| Archivo | `specs/spec-stock-bajo.md` |
| Estado | Spec en borrador (2026-11-02) · Plan y tareas en borrador |
| Constitución | v2.8.0 (secciones 5 y 8) |
| Trazabilidad | CU-09 (prioridad media; incluye CU-20 de n8n) · RF-09 (y RF-29, proceso 3, del lado de n8n) · RN-05 · RNF-08, RNF-22 |
| Depende de | `spec-movimientos.md`, `spec-estado-inventario.md` (`politica-stock-bajo.ts`) |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Contexto

Cuando el stock de un insumo llega a su nivel mínimo, el administrador debe enterarse (RN-05). Este servicio **no envía correos**: publica un evento en RabbitMQ y n8n, suscrito con su propia cola al exchange `eventos`, consulta el insumo y envía la alerta (constitución v2.7.0, proceso 3 del documento de requisitos).

```text
movimiento (manual o Saga) ─commit─▶ ¿stock <= nivelMinimo y sin alerta en 24 h?
                                        └─ sí ─▶ exchange "eventos", routing key inventario.stock.bajo ─▶ cola de n8n ─▶ correo
```

## Escenarios de usuario y pruebas

### Historia 1 — Avisar cuando un insumo llega al nivel mínimo (Prioridad: P1)

Como administrador, quiero que el sistema avise cuando un insumo llega a su nivel mínimo, para reponerlo antes de que falte en una labor.

**Por qué esta prioridad:** es la regla RN-05; sin el evento, n8n no puede alertar.

**Prueba independiente:** con una cola de prueba enlazada al exchange `eventos`, se registra una salida que deja el stock en el mínimo y se lee el evento.

**Escenarios de aceptación:**

1. **Dado** "Urea" con stock 60 y mínimo 50, **cuando** se registra una salida de 10, **entonces** se publica un evento `StockBajo` con routing key `inventario.stock.bajo` y `datos` `{ idInsumo, nombre: "Urea", stock: "50.000", nivelMinimo: "50.000", unidad: "KILOGRAMO" }`, y el insumo guarda `fechaUltimaAlerta`.
2. **Dado** "Urea" con stock 80 y mínimo 50, **cuando** se registra una salida de 10, **entonces** no se publica nada.
3. **Dado** un descuento de la Saga que deja dos insumos bajo el mínimo, **entonces** se publica un evento por cada uno.
4. **Dado** una entrada que deja el stock todavía en o bajo el mínimo (por ejemplo, la compensación de una Saga), **entonces** también se evalúa la regla, porque se evalúa tras cada movimiento (constitución §5).
5. **Dado** el evento publicado, **entonces** su sobre lleva `origen = servicio-inventario`, `version = 1` y el `idCorrelacion` de la solicitud o Saga que causó el movimiento.

---

### Historia 2 — No repetir la alerta más de una vez cada 24 horas (Prioridad: P1)

Como administrador, quiero recibir como máximo una alerta por insumo cada 24 horas, para que las labores sucesivas no me llenen el correo.

**Por qué esta prioridad:** la constitución lo exige y tiene test obligatorio.

**Prueba independiente:** con un reloj fijo, se registran varias salidas y se cuentan los eventos.

**Escenarios de aceptación:**

1. **Dado** que "Urea" generó una alerta a las 10:00, **cuando** a las 15:00 otra salida la deja más baja, **entonces** no se publica un evento nuevo.
2. **Dado** lo mismo, **cuando** al día siguiente a las 10:00 (24 h exactas) otra salida la deja bajo el mínimo, **entonces** se publica un evento nuevo.
3. **Dado** que "Urea" se repuso por encima del mínimo y a las 3 horas vuelve a bajar, **entonces** no se publica un evento nuevo: la regla es "uno cada 24 h por insumo", sin excepción por reposición.
4. **Dado** dos salidas simultáneas que dejan "Urea" bajo el mínimo, **entonces** se publica un solo evento.

---

### Historia 3 — No perder la alerta si RabbitMQ falla (Prioridad: P2)

Como administrador, quiero que una falla del broker no impida registrar movimientos ni marque como enviada una alerta que no salió.

**Por qué esta prioridad:** la constitución exige guardar la fecha solo después de publicar (RNF-08).

**Prueba independiente:** con el publicador simulado para fallar, se registra una salida y luego otra con el publicador sano.

**Escenarios de aceptación:**

1. **Dado** que la publicación falla, **cuando** se registra una salida que deja el stock bajo el mínimo, **entonces** el movimiento queda registrado igual (la respuesta HTTP es `201`), se registra el error en el log con el `idCorrelacion` y `fechaUltimaAlerta` no cambia.
2. **Dado** lo anterior, **cuando** se registra el siguiente movimiento con el publicador sano, **entonces** se publica el evento y se guarda `fechaUltimaAlerta`.

---

### Casos borde

- Cambiar `nivelMinimo` con `PUT /insumos/{id}` no publica el evento, aunque el stock quede bajo el nuevo mínimo; la regla se evalúa tras cada movimiento (constitución §5). `GET /estado-inventario` sí lo muestra como `stockBajo`.
- El proceso se cae entre la reserva y la publicación: la reserva vence a los 60 s y el siguiente movimiento vuelve a intentarlo.
- Un movimiento rechazado (`STOCK_INSUFICIENTE`) no cambia el stock y no evalúa la regla.

## Requisitos

### Requisitos funcionales

- **RQ-SBJ-01**: Después del commit de cada movimiento (manual, stock inicial o Saga), por cada insumo afectado, si `stock <= nivelMinimo` (`politica-stock-bajo.ts`) y no hubo alerta en las últimas 24 h, el servicio publica el evento.
- **RQ-SBJ-02**: El evento se publica en el exchange `eventos` (topic, durable) con routing key `inventario.stock.bajo`, sobre común, `tipo = StockBajo`, `version = 1`, y `datos`: `idInsumo`, `nombre`, `stock`, `nivelMinimo` (texto decimal) y `unidad`. Los valores son los del insumo leído después del commit.
- **RQ-SBJ-03**: Como máximo un evento por insumo cada 24 h, también ante movimientos concurrentes.
- **RQ-SBJ-04**: `fechaUltimaAlerta` se guarda solo después de que RabbitMQ confirma la publicación (publisher confirms).
- **RQ-SBJ-05**: Si la publicación falla, se registra el error en el log, no se guarda `fechaUltimaAlerta` y la respuesta del movimiento no cambia. La alerta se intenta de nuevo en el siguiente movimiento del insumo.
- **RQ-SBJ-06**: El servicio no declara colas para el evento; cada consumidor (n8n u otros) crea la suya enlazada al exchange (constitución §8).
- **RQ-SBJ-07**: El servicio no envía correos ni llama webhooks.

### Entidades clave

- **Insumo**: usa `fechaUltimaAlerta` y `reservaAlertaHasta` (campos ya creados en `spec-insumos.md`).
- **PoliticaStockBajo**: `estaEnStockBajo(stock, nivelMinimo)` y `debeAlertar(insumo, ahora)`.

## Criterios de éxito

- **CE-SBJ-01**: Test obligatorio del evento de stock bajo, incluida la regla de 24 horas (constitución §6), en verde.
- **CE-SBJ-02**: Con 20 salidas concurrentes que dejan un insumo bajo el mínimo, se publica exactamente un evento.
- **CE-SBJ-03**: Con RabbitMQ caído, los movimientos siguen registrándose (RNF-08).
- **CE-SBJ-04**: Publicar el evento no agrega más de 100 ms a la respuesta del movimiento en condiciones normales.

## Supuestos

- n8n consulta `GET /insumos/{id}` con la cuenta de servicio (`lectura_inventario`) antes de enviar el correo, para usar el dato más reciente (constitución v2.7.0).

## Fuera de alcance

- Envío de correos, destinatarios y plantillas (n8n).
- Alertas por otros motivos (vencimiento, sobrestock).

---

# 2. Plan

Primera funcionalidad con RabbitMQ: aquí se agregan la conexión y el publicador que después reutiliza la Saga.

## 2.1 Dependencias y configuración

- Se agregan `amqplib`, `amqp-connection-manager` y, para tests, `@testcontainers/rabbitmq` (`rabbitmq:4-management-alpine`, igual que Docker Compose).
- Variable de entorno `RABBITMQ_URL` (README D-14): `amqp://` en local y tests, `amqps://` en la nube.
- `/salud/readiness` pasa a incluir RabbitMQ (`conexion.isConnected()`).

## 2.2 Publicador

`PublicadorEventosRabbitmq` (`adapters/outbound/messaging`), implementa el puerto `PublicadorEventos`:

- Una conexión de `amqp-connection-manager` y un `ChannelWrapper` con `confirm: true`; en `setup` declara el exchange `eventos` (`topic`, `durable: true`).
- `publicarEvento(routingKey, tipo, datos, idCorrelacion)`: arma el sobre (`idMensaje` nuevo, `fechaOcurrencia`, `origen = servicio-inventario`, `version = 1`) y publica con `persistent: true` y `contentType: application/json`. Resuelve cuando el broker confirma; rechaza si no confirma o si la conexión no está disponible en 5 s.

## 2.3 Regla de 24 h con reserva

Para cumplir a la vez RQ-SBJ-03 (uno cada 24 h, también en concurrencia) y RQ-SBJ-04 (la fecha solo después de publicar), el caso de uso reserva el envío antes de publicar:

```text
EvaluarStockBajoCasoUso.ejecutar(idsInsumo, idCorrelacion)     ← después del commit, sin transacción
  por cada idInsumo:
    1. insumo = repositorio.buscarPorId(idInsumo)
    2. si !politica.debeAlertar(insumo, ahora) → seguir
         debeAlertar = estaEnStockBajo(stock, nivelMinimo)
                       y (fechaUltimaAlerta es null o ahora − fechaUltimaAlerta >= 24 h)
                       y (reservaAlertaHasta es null o reservaAlertaHasta <= ahora)
    3. reservado = repositorio.reservarAlerta(idInsumo, ahora, ahora + 60 s)
         updateOne({ _id, fecha_ultima_alerta: <la leída>, $or: [reserva null, reserva <= ahora] },
                   { $set: { reserva_alerta_hasta: ahora + 60 s } })
       si no se modificó → otro proceso ya la reservó; seguir
    4. publicador.publicarEvento("inventario.stock.bajo", "StockBajo", datos, idCorrelacion)
       ├─ ok   → repositorio.confirmarAlerta(idInsumo, ahora)   ($set fecha_ultima_alerta = ahora, reserva = null)
       └─ error → log de error; repositorio.liberarReserva(idInsumo)   (reserva = null)
```

- La actualización condicionada del paso 3 es atómica: de dos movimientos simultáneos, solo uno reserva.
- Si el proceso se cae entre 3 y 4, la reserva vence en 60 s y el siguiente movimiento reintenta.
- Los fallos de este caso de uso nunca se propagan al movimiento: el controlador y el consumidor de la Saga lo llaman después de responder o de confirmar, y solo registran el error.

## 2.4 Integración con los movimientos

- `RegistrarMovimientoCasoUso` ya devuelve los insumos afectados (`spec-movimientos.md`, 2.2). El controlador REST, después del commit, llama a `EvaluarStockBajoCasoUso` sin esperarlo para responder (`void`, con `catch` que registra el error).
- `CrearInsumoCasoUso` hace lo mismo con el stock inicial.
- La Saga lo llama después de publicar su respuesta (`spec-descuento-saga.md`).

## 2.5 Diseño por capas

| Capa | Archivo | Responsabilidad |
|---|---|---|
| `domain/supply` | `politica-stock-bajo.ts` (se amplía) | `debeAlertar(insumo, ahora)` con la ventana de 24 h y la reserva |
| `application/ports` | `publicador-eventos.puerto.ts`; se amplía `repositorio-insumo.puerto.ts` | `publicarEvento`; `reservarAlerta`, `confirmarAlerta`, `liberarReserva` |
| `application/use-cases` | `evaluar-stock-bajo.caso-uso.ts` | 2.3 |
| `adapters/outbound/messaging` | `conexion-rabbitmq.ts`, `publicador-eventos.rabbitmq.ts` | Conexión, exchange y publicación con confirmación |

## 2.6 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `politica-stock-bajo.spec.ts` (se amplía) | Sin alerta previa; 23 h 59 min; 24 h exactas; reserva vigente y vencida |
| Unitario | `evaluar-stock-bajo.caso-uso.spec.ts` | Reserva perdida → no publica; publicación fallida → libera la reserva y no confirma; éxito → confirma (publicador y repositorio dobles, reloj fijo) |
| Integración | `stock-bajo.int-spec.ts` | Historias 1 y 2 con RabbitMQ real y una cola de prueba enlazada a `eventos` con `inventario.stock.bajo`; reloj fijo inyectado en el módulo de prueba (CE-SBJ-01) |
| Integración | `stock-bajo-concurrencia.int-spec.ts` | CE-SBJ-02 |
| Integración | `stock-bajo-fallos.int-spec.ts` | Historia 3 con el publicador reemplazado por uno que falla; con el broker detenido, los movimientos responden `201` (CE-SBJ-03) |

---

# 3. Tareas

- [ ] **T01** — Agregar las dependencias de RabbitMQ, `RABBITMQ_URL`, la conexión, RabbitMQ en `/salud/readiness` y el contenedor de RabbitMQ en la base de los tests de integración.
- [ ] **T02** — Implementar `PublicadorEventosRabbitmq` con confirmaciones. *Hecho cuando:* un test de integración publica y lee un evento de una cola enlazada.
- [ ] **T03** — Ampliar `politica-stock-bajo.ts` con `debeAlertar`, con sus tests unitarios.
- [ ] **T04** — Implementar `reservarAlerta`, `confirmarAlerta`, `liberarReserva` y `EvaluarStockBajoCasoUso`, con sus tests unitarios.
- [ ] **T05** — Llamar al caso de uso después del commit en `POST /movimientos` y en `POST /insumos`. *Hecho cuando:* pasa `stock-bajo.int-spec.ts`.
- [ ] **T06** — Escribir `stock-bajo-concurrencia.int-spec.ts` y `stock-bajo-fallos.int-spec.ts`.
- [ ] **T07** — Revisar con el equipo de n8n el contrato del evento (RQ-SBJ-02 y el mapa de mensajería de `specs/README.md`): exchange, routing key, sobre y `datos`.
- [ ] **T08** — Verificación final: `npm test` en verde, cobertura ≥ 80 % y criterios CE-SBJ-01 a CE-SBJ-04 cubiertos.
