# Sincronización de operaciones offline — `servicio-operaciones`

| Campo | Valor |
|---|---|
| Servicio | `servicio-operaciones` |
| Archivo | `specs/spec-sincronizacion.md` |
| Estado | Spec en borrador (2026-11-02) |
| Constitución | v2.8.0 (sección 5) |
| Trazabilidad | CU-13 (prioridad media) · RF-14, RF-15, RF-16, RF-17 (lado servidor) · RN-10, RN-11, RN-12 · RNF-09, RNF-14 |
| Depende de | `spec-labores.md`, `spec-incidencias.md` (y `spec-saga.md` para las labores con insumos) |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Contexto

Sin conexión, Vue.js (IndexedDB) y Flutter (SQLite) guardan las labores e incidencias con un UUID generado al crearlas (RF-15). Al recuperar conectividad y con sesión válida de Keycloak (RN-12, del lado del cliente), envían las pendientes en un solo lote (RF-16). Este servicio las procesa en orden cronológico con los **mismos casos de uso** de `spec-labores.md` y `spec-incidencias.md` y devuelve el resultado de cada una por separado, para que la app muestre su estado y motivo (RF-17, RNF-14). El fallo de una no aborta el lote (constitución §5).

```text
POST /sincronizacion  [op3 (10:02), op1 (09:15), op2 (09:40)]
   └─▶ ordena por fechaCreacion ─▶ op1 ─▶ op2 ─▶ op3
   ◀── [op1 SINCRONIZADA, op2 ERROR CAMPANIA_FINALIZADA, op3 SINCRONIZADA]
```

## Escenarios de usuario y pruebas

### Historia 1 — Sincronizar un lote con resultados mixtos (Prioridad: P1)

Como técnico de campo, quiero enviar todo lo que registré sin conexión y ver qué se sincronizó y qué falló, para corregir solo lo que falló (RF-16, RF-17).

**Por qué esta prioridad:** es el test obligatorio de la constitución §8 (resultados mixtos y orden cronológico).

**Prueba independiente:** con gestión simulada, se envía un lote desordenado con operaciones válidas e inválidas.

**Escenarios de aceptación:**

1. **Dado** un lote con una labor realizada sin insumos, una labor programada y una incidencia con foto, todas válidas, **entonces** responde `200` con un resultado `SINCRONIZADA` por operación, con `idRecurso` y, en las labores, su `estado` (`CONFIRMADA`, `PROGRAMADA`).
2. **Dado** un lote con `fechaCreacion` desordenadas, **entonces** se procesan y se devuelven en orden cronológico (empate: por `idOperacion`).
3. **Dado** que la segunda operación es una labor en una campaña finalizada, **entonces** su resultado es `ERROR` con `codigo = CAMPANIA_FINALIZADA`, `mensaje`, `reintentable = false`, y la primera y la tercera se sincronizan igual.
4. **Dado** una labor programada y su realización en el mismo lote (la realización con `fechaCreacion` posterior), **entonces** ambas se sincronizan: la programación se procesa antes.
5. **Dado** una realización cuya labor programada viene en el mismo lote con `fechaCreacion` **posterior**, **entonces** la realización da `ERROR` `LABOR_NO_ENCONTRADA` y la programación se sincroniza; la app la reenvía en el siguiente lote.
6. **Dado** una labor con insumos, **entonces** su resultado es `SINCRONIZADA` con `estado = PENDIENTE`; el estado final lo consulta la app con `GET /labores/{id}`.

---

### Historia 2 — Reenviar un lote sin duplicar (Prioridad: P1)

Como técnico de campo, quiero que si se corta la conexión a mitad de la sincronización pueda reenviar el lote completo sin duplicar nada (RN-10, RNF-09).

**Escenarios de aceptación:**

1. **Dado** un lote ya procesado, **cuando** se reenvía igual, **entonces** cada operación vuelve `SINCRONIZADA` con `repetida = true` y el mismo `idRecurso`, sin efectos nuevos.
2. **Dado** una operación del lote con el mismo `idOperacion` y otro contenido que una ya sincronizada, **entonces** su resultado es `ERROR` `CONFLICTO_IDEMPOTENCIA`, `reintentable = false`.
3. **Dado** el mismo `idOperacion` dos veces en un lote con el mismo contenido, **entonces** la primera se sincroniza y la segunda vuelve `SINCRONIZADA` con `repetida = true`.

---

### Historia 3 — No perder operaciones ante fallos (Prioridad: P1)

Como técnico de campo, quiero que una caída de otro servicio o un fallo técnico no me haga perder lo registrado (RNF-08, RNF-09).

**Escenarios de aceptación:**

1. **Dado** que `servicio-gestion` no responde, **entonces** las labores del lote se sincronizan con `estado = PENDIENTE` (validación diferida, `spec-labores.md` Historia 4), no como error.
2. **Dado** que DynamoDB o S3 fallan con una operación, **entonces** su resultado es `ERROR` `ERROR_INTERNO` con `reintentable = true` (la app la conserva pendiente y la reenvía) y el lote continúa con las siguientes.
3. **Dado** un lote donde todas las operaciones de una misma campaña consultan gestión, **entonces** la campaña se consulta una sola vez por lote.

---

### Historia 4 — Rechazar lotes mal formados (Prioridad: P2)

**Escenarios de aceptación:**

1. **Dado** una solicitud sin la parte `operaciones`, con un JSON que no es una lista, con 0 o más de 50 operaciones, o de más de 40 MB, **entonces** responde `400 DATOS_INVALIDOS` sin procesar ninguna.
2. **Dado** una operación sin `tipo` válido, sin `datos.idOperacion` UUID o sin `datos.fechaCreacion` válida, **entonces** su resultado es `ERROR` `DATOS_INVALIDOS` (con `idOperacion` si se pudo leer), se devuelve al final y el resto se procesa.
3. **Dado** una incidencia cuya foto no viene en el lote, **entonces** su resultado es `ERROR` `DATOS_INVALIDOS`.
4. **Dado** un usuario sin `tecnico_campo`, **entonces** responde `403 SIN_PERMISO`; sin token o con token vencido, `401 NO_AUTENTICADO` (la app vuelve al login, RN-12).

---

### Casos borde

- Un error de permiso dentro del lote no puede ocurrir: el técnico puede programar y registrar; el permiso se verifica una vez para el lote.
- Una operación tarda porque gestión llega al tiempo límite (2 s): el lote sigue; con la caché por campaña, una campaña caída cuesta 2 s una sola vez.
- Dos lotes simultáneos del mismo técnico con operaciones en común: la idempotencia de cada caso de uso garantiza un solo recurso por `idOperacion`.
- La sesión vence durante el lote: no afecta, el token se valida al recibir la solicitud.

## Requisitos

### Requisitos funcionales

- **RQ-SIN-01**: `POST /sincronizacion` (`multipart/form-data`, rol `tecnico_campo`) recibe la parte `operaciones` (lista JSON de 1 a 50 elementos) y una parte de archivo por cada incidencia, con nombre `fotos[<idOperacion>]`. Cuerpo total de hasta 40 MB.
- **RQ-SIN-02**: Cada operación es `{ tipo, datos }`:

  | `tipo` | `datos` | Caso de uso |
  |---|---|---|
  | `REGISTRAR_LABOR` | El cuerpo de `POST /labores` | `ProgramarLaborCasoUso` o `RegistrarLaborCasoUso` |
  | `REALIZAR_LABOR` | El cuerpo de `POST /labores/{id}/realizacion` más `idLabor` | `RealizarLaborCasoUso` |
  | `REGISTRAR_INCIDENCIA` | La parte `datos` de `POST /incidencias`; la foto es `fotos[<idOperacion>]` | `RegistrarIncidenciaCasoUso` |

- **RQ-SIN-03**: Las operaciones se procesan en orden ascendente de `datos.fechaCreacion` y, a igual fecha, de `idOperacion` (RN-11, constitución §5). Las que no tienen sobre válido (Historia 4, escenario 2) no se procesan y se devuelven al final.
- **RQ-SIN-04**: Cada operación pasa por las mismas validaciones, reglas e idempotencia que su endpoint individual (RQ-LAB-* y RQ-INC-*). El lote no agrega reglas propias.
- **RQ-SIN-05**: El fallo de una operación (de negocio o técnico) no aborta el lote. Un fallo técnico se registra en el log con el `idOperacion` y el `idCorrelacion`.
- **RQ-SIN-06**: Respuesta `200` con `resultados` (en el orden de procesamiento) y `resumen`:

  | Campo | Valor |
  |---|---|
  | `idOperacion` | El de la operación, o `null` si no se pudo leer |
  | `tipo` | El de la operación |
  | `resultado` | `SINCRONIZADA` / `ERROR` |
  | `repetida` | `true` si ya estaba procesada (solo con `SINCRONIZADA`) |
  | `idRecurso`, `estado` | ID de la labor o incidencia y, en labores, su estado actual |
  | `codigo`, `mensaje`, `detalles` | Los del error, con los mismos códigos del endpoint individual (solo con `ERROR`) |
  | `reintentable` | `true` solo para `ERROR_INTERNO` |

- **RQ-SIN-07**: Dentro de un lote, el estado de cada campaña se consulta a gestión una sola vez (caché en memoria de la solicitud, también para "no disponible").
- **RQ-SIN-08**: El lote no se audita como tal; se audita cada operación con su acción normal.

### Entidades clave

No introduce entidades nuevas. **ResultadoSincronizacion**: `SINCRONIZADA` / `ERROR` (glosario).

## Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Sin `operaciones`, no es una lista JSON, 0 o más de 50 operaciones, cuerpo de más de 40 MB |
| 401 | `NO_AUTENTICADO` | Sin token o token inválido |
| 403 | `SIN_PERMISO` | Sin `tecnico_campo` |

Los errores de cada operación van en su resultado, nunca como código HTTP del lote.

## Criterios de éxito

- **CE-SIN-01**: Test obligatorio de la constitución §8 en verde: lote con resultados mixtos procesado en orden cronológico.
- **CE-SIN-02**: Reenviar un lote completo cualquier número de veces no crea recursos nuevos ni cambia los existentes.
- **CE-SIN-03**: Un lote de 50 labores sin fotos de 5 campañas responde en menos de 5 s con gestión respondiendo en 50 ms; con gestión caída, en menos de 15 s.
- **CE-SIN-04**: Ninguna operación de un lote aceptado queda sin resultado.

## Supuestos

- La app divide en varios lotes lo que supere 50 operaciones o 40 MB, y los envía en orden cronológico.
- La app conserva las operaciones con `ERROR` no reintentable para que el usuario las revise, sin borrarlas (RN-11), y reenvía las reintentables.
- La verificación de conectividad y de sesión antes de sincronizar (RN-12) la hace la app; el servidor solo exige un JWT válido.

## Aclaraciones

- **AC-01** — Resuelta (2026-11-02): fotos en el mismo lote como partes `multipart` (README, historial).

## Fuera de alcance

- Descarga de datos para trabajar sin conexión (cada app la hace con los `GET` de cada servicio).
- Resolución de conflictos de edición: las operaciones solo crean o realizan, nunca editan.

---

# 2. Plan

No crea tablas ni dependencias. Orquesta los casos de uso existentes.

## 2.1 Endpoint

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /sincronizacion` (`multipart/form-data`) | `tecnico_campo` | `200` + resultados | 400, 401, 403 |

**Parte `operaciones`:**

```json
[
  {
    "tipo": "REGISTRAR_LABOR",
    "datos": {
      "idOperacion": "uuid-1",
      "fechaCreacion": "2026-11-02T09:15:00Z",
      "tipoLabor": "RIEGO",
      "idParcela": "uuid",
      "idCampania": "uuid",
      "fechaEjecucion": "2026-11-02T09:00:00Z"
    }
  },
  {
    "tipo": "REGISTRAR_INCIDENCIA",
    "datos": {
      "idOperacion": "uuid-2",
      "fechaCreacion": "2026-11-02T09:40:00Z",
      "tipo": "PLAGA",
      "descripcion": "Pulgón en el sector sur",
      "fechaObservacion": "2026-11-02T09:38:00Z",
      "idParcela": "uuid"
    }
  }
]
```

Con la parte de archivo `fotos[uuid-2]`.

**Respuesta:**

```json
{
  "resultados": [
    { "idOperacion": "uuid-1", "tipo": "REGISTRAR_LABOR", "resultado": "SINCRONIZADA", "repetida": false, "idRecurso": "uuid-1", "estado": "CONFIRMADA" },
    { "idOperacion": "uuid-2", "tipo": "REGISTRAR_INCIDENCIA", "resultado": "ERROR", "codigo": "FOTO_INVALIDA", "mensaje": "La fotografía debe ser JPEG o PNG de hasta 10 MB.", "detalles": [], "reintentable": false }
  ],
  "resumen": { "sincronizadas": 1, "errores": 1 }
}
```

## 2.2 Flujo

```text
SincronizarOperacionesCasoUso.ejecutar(operaciones, fotos, usuario):
  1. Separar las de sobre inválido (resultado DATOS_INVALIDOS, al final).
  2. Ordenar el resto por (fechaCreacion, idOperacion).
  3. pasarela = PasarelaCampaniaConCache(pasarelaCampania)       ← una consulta por campaña en el lote
  4. por cada operación:
       try:
         validar datos con las reglas del endpoint (ValidadorOperacion por tipo) → DATOS_INVALIDOS
         resultado = casoDeUso[tipo].ejecutar(entrada, usuario, pasarela)
         → SINCRONIZADA (repetida si el caso de uso lo indica)
       catch ExcepcionDominio e → ERROR(e.codigo, e.mensaje, e.detalles, reintentable = false)
       catch cualquier otra     → log; ERROR(ERROR_INTERNO, reintentable = true)
  5. Devolver resultados y resumen.
```

- Los casos de uso de labores e incidencias ya devuelven si la operación era repetida (lo usan para elegir `201` o `200`); aquí se usa para `repetida`.
- Las reglas de validación de los `FormRequest` se extraen a clases `ReglasLabor`, `ReglasRealizacion` y `ReglasIncidencia`, compartidas por los endpoints y por `ValidadorOperacion`, para que el lote valide exactamente igual.
- `PasarelaCampaniaConCache` es un decorador de `PasarelaCampania` en `Application` (sin infraestructura), creado por solicitud.

## 2.3 Diseño por capas

| Capa | Archivo | Responsabilidad |
|---|---|---|
| `Application/UseCases/SyncOfflineOperations` | `SincronizarOperacionesCasoUso.php`, `OperacionSincronizacion.php`, `ResultadoOperacion.php`, `PasarelaCampaniaConCache.php` | 2.2 |
| `Domain/Shared` | `ResultadoSincronizacion.php` | `SINCRONIZADA` / `ERROR` |
| `InterfaceAdapters/Http` | `SincronizacionControlador.php`, `Requests/SincronizacionRequest.php`, `Validacion/ValidadorOperacion.php`, `Validacion/Reglas*.php` | Lectura de partes, validación del lote y de cada operación |

## 2.4 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `tests/Unit/Application/SincronizarOperacionesCasoUsoTest.php` | Orden y desempate, sobre inválido al final, error técnico reintentable, caché de campaña |
| Integración | `tests/Integration/Http/SincronizacionTest.php` | Historias 1, 3 y 4 con DynamoDB Local, LocalStack y gestión simulada (CE-SIN-01, CE-SIN-04) |
| Integración | `tests/Integration/Http/SincronizacionIdempotenciaTest.php` | Historia 2 (CE-SIN-02) |
| Integración | `tests/Integration/Http/SincronizacionRendimientoTest.php` | CE-SIN-03 con gestión simulada con demora |

---

# 3. Tareas

- [ ] **T01** — Extraer las reglas de los `FormRequest` de labores, realización e incidencias a `Reglas*` sin cambiar el comportamiento. *Hecho cuando:* los tests de `spec-labores.md` y `spec-incidencias.md` siguen en verde.
- [ ] **T02** — Implementar `PasarelaCampaniaConCache` y `SincronizarOperacionesCasoUso`, con su test unitario.
- [ ] **T03** — Implementar `POST /sincronizacion`. *Hecho cuando:* pasan `SincronizacionTest.php` y `SincronizacionIdempotenciaTest.php`.
- [ ] **T04** [P] — Escribir `SincronizacionRendimientoTest.php` y documentar el endpoint en `openapi.yaml`.
- [ ] **T05** — Verificación final: `vendor/bin/pest --coverage --min=80` en verde y criterios CE-SIN-01 a CE-SIN-04 cubiertos.
