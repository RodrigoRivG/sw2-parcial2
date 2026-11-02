# Movimientos de inventario — `servicio-inventario`

| Campo | Valor |
|---|---|
| Servicio | `servicio-inventario` |
| Archivo | `specs/spec-movimientos.md` |
| Estado | Spec en borrador (2026-11-02) · Plan y tareas en borrador |
| Constitución | v2.8.0 (secciones 3 y 4) |
| Trazabilidad | CU-07 (prioridad alta) · RF-08 · RN-04, RN-15, RN-16 · RNF-05 |
| Depende de | `spec-insumos.md` |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Contexto

El stock de un insumo solo cambia mediante movimientos (constitución §3). Hay tres orígenes:

| Origen | Tipo | Quién lo crea | Archivo |
|---|---|---|---|
| Stock inicial | `ENTRADA` | Al crear el insumo | `spec-insumos.md` |
| Manual (compra, ajuste, merma) | `ENTRADA` o `SALIDA` | Administrador, por REST | Este archivo |
| Saga | `SALIDA` (descuento) o `ENTRADA` (compensación) | Comandos de `servicio-operaciones` | `spec-descuento-saga.md` |

Todos comparten la misma regla de dominio y la misma operación de persistencia, que se definen aquí.

## Escenarios de usuario y pruebas

### Historia 1 — Registrar una entrada (Prioridad: P1)

Como administrador, quiero registrar la llegada de insumos, para que el stock refleje lo que hay en el almacén.

**Por qué esta prioridad:** sin entradas el stock solo baja; es la forma normal de reponer.

**Prueba independiente:** se registra una entrada y se verifican el movimiento y el stock del insumo.

**Escenarios de aceptación:**

1. **Dado** "Urea 46 %" con stock 120 kg, **cuando** el administrador registra una `ENTRADA` de `"80"` con motivo "Compra factura 1234", **entonces** se crea el movimiento con `stockResultante` `"200.000"`, el costo unitario vigente del insumo y su auditoría, y el insumo queda con stock 200 kg.
2. **Dado** un insumo con unidad `UNIDAD`, **cuando** se registra una entrada de `"2.5"`, **entonces** se rechaza con `422 CANTIDAD_INVALIDA`.
3. **Dado** una cantidad `"0"` o negativa, **entonces** se rechaza con `422 CANTIDAD_INVALIDA`.
4. **Dado** un `idInsumo` inexistente, **entonces** se rechaza con `404 INSUMO_NO_ENCONTRADO`.

---

### Historia 2 — Registrar una salida manual (Prioridad: P1)

Como administrador, quiero registrar salidas que no vienen de una labor (merma, vencimiento, corrección de un error), para que el stock no quede inflado.

**Por qué esta prioridad:** los errores de carga se corrigen con un movimiento inverso, no editando (constitución §4).

**Prueba independiente:** se registra una salida con y sin stock suficiente.

**Escenarios de aceptación:**

1. **Dado** stock 200 kg, **cuando** se registra una `SALIDA` de `"30"` con motivo "Bolsa rota", **entonces** el stock queda en 170 kg y el movimiento tiene `stockResultante` `"170.000"`.
2. **Dado** stock 170 kg, **cuando** se registra una `SALIDA` de `"170"`, **entonces** se acepta y el stock queda en 0.
3. **Dado** stock 170 kg, **cuando** se registra una `SALIDA` de `"170.001"`, **entonces** se rechaza con `422 STOCK_INSUFICIENTE`, el stock no cambia y no se crea movimiento (RN-04).
4. **Dado** un usuario `gerencia` o `tecnico_campo`, **cuando** intenta registrar un movimiento, **entonces** recibe `403 SIN_PERMISO`. Los técnicos consumen insumos solo a través de las labores (Saga).

---

### Historia 3 — Consultar movimientos (Prioridad: P2)

Como administrador o gerente, quiero ver el historial de movimientos de un insumo, para entender cómo llegó a su stock actual.

**Por qué esta prioridad:** da trazabilidad, pero el servicio funciona sin ella.

**Prueba independiente:** con movimientos manuales y de la Saga, se filtran por insumo, tipo y fechas.

**Escenarios de aceptación:**

1. **Dado** 25 movimientos de un insumo, **cuando** se listan con `idInsumo`, **entonces** se reciben los 20 más recientes, ordenados por fecha descendente, con el total.
2. **Dado** el filtro `tipo=SALIDA` y un rango `desde`/`hasta`, **entonces** solo se reciben las salidas de ese rango.
3. **Dado** el filtro `idSaga`, **entonces** se reciben los movimientos de esa Saga (descuento y, si hubo, compensación).
4. **Dado** un movimiento de la Saga, **entonces** incluye `idSaga`, `idLabor` y como `actor` el servicio de origen.
5. **Dado** un ID de movimiento inexistente, **entonces** se recibe `404 MOVIMIENTO_NO_ENCONTRADO`.

---

### Casos borde

- Dos salidas simultáneas sobre el mismo insumo cuya suma supera el stock: una se acepta y la otra recibe `422 STOCK_INSUFICIENTE`; el stock nunca queda negativo.
- Una salida manual y un descuento de la Saga simultáneos: la misma garantía (la regla vive en la operación común).
- Motivo vacío o de más de 200 caracteres: `400 DATOS_INVALIDOS`.
- Intento de enviar `idSaga` o `idLabor` en un movimiento manual: `400 DATOS_INVALIDOS` (campo no permitido).
- Rango de fechas invertido (`desde` > `hasta`): `400 DATOS_INVALIDOS`.
- No existe `PUT` ni `DELETE` sobre movimientos: los movimientos son inmutables (responde `404 RECURSO_NO_ENCONTRADO`).

## Requisitos

### Requisitos funcionales

- **RQ-MOV-01**: El sistema debe permitir registrar un movimiento manual con:
  - `idInsumo`: obligatorio, UUID de un insumo existente.
  - `tipo`: obligatorio, `ENTRADA` o `SALIDA`.
  - `cantidad`: obligatoria, decimal > 0 en la unidad del insumo, hasta 3 decimales (entero con `UNIDAD`).
  - `motivo`: obligatorio, de 1 a 200 caracteres.
- **RQ-MOV-02**: Una `SALIDA` mayor al stock disponible se rechaza completa con `422 STOCK_INSUFICIENTE`, sin cambios (RN-04).
- **RQ-MOV-03**: El cambio de stock, el movimiento y su auditoría se guardan en la misma transacción (constitución §4).
- **RQ-MOV-04**: La salida usa una actualización atómica condicionada (`stock >= cantidad`), para que dos operaciones simultáneas nunca dejen stock negativo (constitución §4).
- **RQ-MOV-05**: Cada movimiento guarda: `id`, `idInsumo`, `tipo`, `cantidad`, `stockResultante`, `costoUnitario` vigente al momento del movimiento, `motivo`, `actor`, `fecha` y, si viene de la Saga, `idSaga` e `idLabor`.
- **RQ-MOV-06**: Los movimientos son inmutables: no se editan ni se borran (constitución §4).
- **RQ-MOV-07**: El primer movimiento de un insumo marca `tieneMovimientos = true`, lo que bloquea el cambio de unidad (`spec-insumos.md`).
- **RQ-MOV-08**: El sistema debe listar movimientos paginados, ordenados por fecha descendente, con filtros opcionales `idInsumo`, `tipo`, `idSaga`, `desde` y `hasta`, y devolver un movimiento por ID.
- **RQ-MOV-09**: Después del commit, todo movimiento evalúa la regla de stock bajo (`spec-stock-bajo.md`). Hasta implementar esa spec, el punto de extensión existe pero no hace nada.

### Entidades clave

- **MovimientoInventario**: los campos de RQ-MOV-05.
- **TipoMovimiento**: `ENTRADA` / `SALIDA`.

## Permisos

| Operación | Roles |
|---|---|
| Registrar entradas y salidas | `administrador` |
| Listar y ver detalle | `administrador`, `gerencia` (constitución v2.8.0) |

## Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Formato, campos ausentes o no permitidos, motivo vacío o largo, decimales de más, rango de fechas invertido |
| 404 | `INSUMO_NO_ENCONTRADO` | El `idInsumo` no existe |
| 404 | `MOVIMIENTO_NO_ENCONTRADO` | El ID de movimiento no existe |
| 422 | `CANTIDAD_INVALIDA` | Cantidad ≤ 0, o decimal con unidad `UNIDAD` |
| 422 | `STOCK_INSUFICIENTE` | La salida supera el stock disponible |

`STOCK_INSUFICIENTE` lleva en `detalles` el stock disponible y la cantidad solicitada.

## Criterios de éxito

- **CE-MOV-01**: Con 50 salidas concurrentes sobre un insumo con stock para 10, se aceptan exactamente 10 y el stock final es 0, nunca negativo.
- **CE-MOV-02**: Para todo insumo, `stock` = suma de entradas − suma de salidas, y el `stockResultante` del último movimiento coincide con el stock.
- **CE-MOV-03**: Todo movimiento tiene su registro de auditoría.
- **CE-MOV-04**: El listado responde en menos de 3 s con 10.000 movimientos cargados (RNF-05).

## Supuestos

- El costo unitario de una entrada no cambia el costo unitario del insumo; si cambió el precio, el administrador lo actualiza con `PUT /insumos/{id}`.

## Aclaraciones

- **AC-01** — Resuelta (constitución v2.8.0): lectura de movimientos para `administrador` y `gerencia`, no para `lectura_inventario`.

## Fuera de alcance

- Edición y borrado de movimientos.
- Transferencias entre almacenes (hay un solo almacén).
- Movimientos con proveedor, factura o lote como campos propios (el motivo es texto libre).

---

# 2. Plan

Reutiliza la Fase 0 y el insumo de `spec-insumos.md`. Criterio: una sola operación de persistencia para los tres orígenes de movimiento.

## 2.1 Regla de dominio

`MovimientoInventario` (`domain/movement`) se crea con `MovimientoInventario.registrar({ insumo, tipo, cantidad, motivo, actor, ahora, idSaga?, idLabor? })`:

- Valida la cantidad con `Cantidad.de(texto, insumo.unidad)` y que sea > 0 (`CANTIDAD_INVALIDA`).
- Para `SALIDA`, valida contra el stock leído (`STOCK_INSUFICIENTE`). Es la validación de negocio; la garantía ante concurrencia la da la persistencia (2.3).
- Calcula `stockResultante` y copia `costoUnitario` del insumo.

## 2.2 Caso de uso

`RegistrarMovimientoCasoUso` (`application/use-cases/registrar-movimiento.caso-uso.ts`):

```text
ejecutar(entrada, actor)              ← siempre dentro de UnidadTrabajo
  1. insumo = repositorioInsumo.buscarPorId(idInsumo)      → 404 si no existe
  2. movimiento = MovimientoInventario.registrar(...)       → 422 si la regla falla
  3. stockNuevo = repositorioInsumo.aplicarMovimiento(idInsumo, tipo, cantidad)
       → null si la salida ya no alcanza (otra operación ganó la carrera) → STOCK_INSUFICIENTE
  4. movimiento.stockResultante = stockNuevo
  5. repositorioMovimiento.guardar(movimiento)
  6. auditoria.registrar({ actor, accion: REGISTRAR_MOVIMIENTO, entidad: MovimientoInventario, idEntidad })
  7. devuelve el movimiento y deja el idInsumo en la lista "evaluar stock bajo después del commit"
```

- El controlador REST abre la transacción con un solo movimiento. `CrearInsumoCasoUso` (stock inicial) y la Saga llaman a `registrarDentroDeTransaccion` para varios movimientos en una sola transacción.
- La lista de insumos a evaluar se devuelve al llamador, que la entrega a `spec-stock-bajo.md` tras el commit.

## 2.3 Persistencia

`RepositorioInsumoMongo.aplicarMovimiento(id, tipo, cantidad)`:

```ts
findOneAndUpdate(
  tipo === 'SALIDA'
    ? { _id: id, stock: { $gte: Decimal128(cantidad) } }
    : { _id: id },
  {
    $inc: { stock: Decimal128(tipo === 'SALIDA' ? -cantidad : cantidad) },
    $set: { tiene_movimientos: true, fecha_actualizacion: ahora },
  },
  { new: true, session },
)
```

- MongoDB compara y suma `Decimal128` con exactitud; no se usa `number`.
- No incrementa `version` (README D-05).
- Dentro de una transacción, dos escrituras simultáneas sobre el mismo insumo producen un `WriteConflict`; `withTransaction` reintenta la perdedora, que en el reintento ve el stock nuevo. Si ya no alcanza, el filtro no coincide y el caso de uso responde `STOCK_INSUFICIENTE`.

Colección `movimientos_inventario`:

| Campo | Tipo |
|---|---|
| `_id` | `String` (UUID) |
| `id_insumo` | `String` |
| `tipo` | `String` |
| `cantidad`, `stock_resultante` | `Decimal128` |
| `costo_unitario` | `Decimal128` |
| `motivo` | `String` |
| `actor` | `String` |
| `id_saga`, `id_labor` | `String` (solo Saga) |
| `fecha` | `Date` |

**`003-crear-indices-movimientos.ts`**: `{ id_insumo: 1, fecha: -1 }`, `{ fecha: -1 }` y `{ id_saga: 1 }` con `partialFilterExpression: { id_saga: { $exists: true } }`.

## 2.4 Endpoints

Prefijo: `/api/inventario/v1`.

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /movimientos` | `administrador` | `201` + `Location` + movimiento | 400, 401, 403, 404 `INSUMO_NO_ENCONTRADO`, 422 |
| `GET /movimientos?idInsumo=&tipo=&idSaga=&desde=&hasta=&pagina=&tamanio=` | `administrador`, `gerencia` | `200` + página | 400, 401, 403 |
| `GET /movimientos/{id}` | `administrador`, `gerencia` | `200` + movimiento | 401, 403, 404 `MOVIMIENTO_NO_ENCONTRADO` |

**Solicitud:**

```json
{
  "idInsumo": "0b6f…",
  "tipo": "ENTRADA",
  "cantidad": "80",
  "motivo": "Compra factura 1234"
}
```

**Respuesta de movimiento:**

```json
{
  "id": "9e2a…",
  "idInsumo": "0b6f…",
  "tipo": "ENTRADA",
  "cantidad": "80.000",
  "stockResultante": "200.000",
  "costoUnitario": "4.8500",
  "motivo": "Compra factura 1234",
  "actor": "5c1d…",
  "idSaga": null,
  "idLabor": null,
  "fecha": "2026-11-02T14:00:00Z"
}
```

**Validaciones del DTO:** `idInsumo` `@IsUUID()`, `tipo` `@IsEnum(TipoMovimiento)`, `cantidad` `@IsString()` + `@Matches(/^-?\d{1,12}(\.\d{1,3})?$/)`, `motivo` `@IsString()` recortado, longitud 1 a 200. En la consulta: `desde` y `hasta` `@IsISO8601()`, `idInsumo` e `idSaga` `@IsUUID()`.

## 2.5 Diseño por capas

| Capa | Archivo | Responsabilidad |
|---|---|---|
| `domain/movement` | `movimiento-inventario.entidad.ts`, `tipo-movimiento.enum.ts` | Regla de 2.1 |
| `application/ports` | `repositorio-movimiento.puerto.ts`; se amplía `repositorio-insumo.puerto.ts` | `guardar`, `buscarPorId`, `listar`, `listarPorSaga(idSaga, tipo)`; `aplicarMovimiento` |
| `application/use-cases` | `registrar-movimiento.caso-uso.ts`, `consultar-movimientos.caso-uso.ts` | 2.2 y consultas |
| `adapters/outbound/persistence` | `movimiento-inventario.esquema.ts`, mapper, `repositorio-movimiento.mongo.ts` | 2.3 |
| `adapters/inbound/http` | `movimientos.controlador.ts`, `dto/` | HTTP ↔ caso de uso |

## 2.6 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `movimiento-inventario.entidad.spec.ts` | Cantidad ≤ 0, decimales con `UNIDAD`, salida mayor al stock, salida igual al stock, `stockResultante` y copia del costo |
| Unitario | `registrar-movimiento.caso-uso.spec.ts` | 404, carrera perdida (`aplicarMovimiento` devuelve `null`) → `STOCK_INSUFICIENTE`, auditoría |
| Integración | `movimientos.controlador.int-spec.ts` | Historias 1 a 3 y casos borde, con auditoría |
| Integración | `movimientos-concurrencia.int-spec.ts` | CE-MOV-01 (50 salidas en paralelo) y CE-MOV-02 |
| Integración | `insumos.controlador.int-spec.ts` (se amplía) | Escenario 1 de la Historia 1 de `spec-insumos.md` (stock inicial) y escenarios 3 y 5 de su Historia 3 |
| Integración | `movimientos-rendimiento.int-spec.ts` | CE-MOV-04 |

---

# 3. Tareas

- [ ] **T01** — Crear `MovimientoInventario` y `TipoMovimiento`, con sus tests unitarios.
- [ ] **T02** — Crear `003-crear-indices-movimientos.ts`, el esquema, el mapper, `RepositorioMovimientoMongo` y `aplicarMovimiento` en `RepositorioInsumoMongo`.
- [ ] **T03** — Implementar `RegistrarMovimientoCasoUso` y `POST /movimientos`; conectar el stock inicial de `CrearInsumoCasoUso`. *Hecho cuando:* pasan las Historias 1 y 2, y el escenario 1 de la Historia 1 de `spec-insumos.md`.
- [ ] **T04** — Completar los escenarios 3 y 5 de la Historia 3 de `spec-insumos.md` (unidad bloqueada, `PUT` aceptado tras un movimiento).
- [ ] **T05** — Implementar `ConsultarMovimientosCasoUso` y los dos `GET`. *Hecho cuando:* pasa la Historia 3 (el escenario 4 se completa en `spec-descuento-saga.md`).
- [ ] **T06** — Escribir `movimientos-concurrencia.int-spec.ts` (CE-MOV-01, CE-MOV-02).
- [ ] **T07** [P] — Escribir `movimientos-rendimiento.int-spec.ts` (CE-MOV-04).
- [ ] **T08** — Documentar en OpenAPI los códigos de error, incluido el `detalles` de `STOCK_INSUFICIENTE`.
- [ ] **T09** — Verificación final: `npm test` en verde, cobertura ≥ 80 % y criterios CE-MOV-01 a CE-MOV-04 cubiertos.
