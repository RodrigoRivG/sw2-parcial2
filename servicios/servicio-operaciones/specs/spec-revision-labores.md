# Resolución de labores en revisión — `servicio-operaciones`

| Campo | Valor |
|---|---|
| Servicio | `servicio-operaciones` |
| Archivo | `specs/spec-revision-labores.md` |
| Estado | Spec en borrador (2026-11-02) |
| Constitución | v2.8.0 (secciones 4, 6 y 9) |
| Trazabilidad | CU-12 (prioridad alta) · RF-13 · RN-08, RN-15, RN-16 · RNF-14 |
| Depende de | `spec-labores.md`, `spec-saga.md` |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Contexto

Una labor queda `PENDIENTE_REVISION` cuando la Saga no pudo completarse (`spec-saga.md`). Cuando la Saga termina, solo hay dos situaciones posibles, y el administrador decide qué hacer con la labor (constitución §9: "Resolver labores `PENDIENTE_REVISION`"):

| Estado de la Saga | Qué pasó | Decisiones posibles |
|---|---|---|
| `COMPENSADA` | Los insumos se devolvieron y no hay costo vigente | `RECHAZAR` (la labor no cuenta) o `REINTENTAR` (nueva Saga, por ejemplo si gestión o inventario estuvieron caídos) |
| `REQUIERE_INTERVENCION` | La anulación del costo se rechazó porque la campaña ya estaba finalizada: el descuento y el costo siguen vigentes y son coherentes | `CONFIRMAR` |

## Escenarios de usuario y pruebas

### Historia 1 — Resolver una labor en revisión (Prioridad: P1)

Como administrador, quiero cerrar las labores que quedaron en revisión, para que ninguna quede pendiente para siempre y los técnicos vean su resultado final.

**Por qué esta prioridad:** sin esto, `PENDIENTE_REVISION` sería un estado sin salida.

**Prueba independiente:** se preparan labores en revisión con su Saga en cada estado y se resuelven.

**Escenarios de aceptación:**

1. **Dado** L1 en revisión con Saga `COMPENSADA`, **cuando** el administrador la resuelve con `RECHAZAR` y una observación, **entonces** L1 queda `RECHAZADA` con `motivo.codigo = RECHAZADA_EN_REVISION`, `resolucion` guarda decisión, observación, administrador, fecha y el motivo anterior, y se audita `RESOLVER_LABOR`.
2. **Dado** lo mismo con `REINTENTAR`, **entonces** L1 vuelve a `PENDIENTE` con `motivo = null`, el `idSaga` anterior pasa a `idsSagaAnteriores`, se crea una Saga nueva y se envía `DescontarInsumos` con el nuevo `idSaga` (`spec-saga.md`, RQ-SAG-01).
3. **Dado** L2 en revisión con Saga `REQUIERE_INTERVENCION`, **cuando** se resuelve con `CONFIRMAR`, **entonces** L2 queda `CONFIRMADA` con su `resolucion`.
4. **Dado** una decisión que no corresponde al estado de la Saga (por ejemplo, `CONFIRMAR` con Saga `COMPENSADA`), **entonces** recibe `422 DECISION_NO_PERMITIDA` con las decisiones permitidas en `detalles`.
5. **Dado** una labor en revisión cuya Saga todavía compensa (`COMPENSANDO`), **entonces** recibe `409 SAGA_EN_CURSO`.
6. **Dado** una labor que no está `PENDIENTE_REVISION`, **entonces** recibe `422 LABOR_NO_EN_REVISION`.
7. **Dado** `REINTENTAR` y gestión responde que la campaña ya está `FINALIZADA`, **entonces** recibe `422 CAMPANIA_FINALIZADA` y la labor no cambia (corresponde `RECHAZAR`). Si gestión no responde, el reintento sigue igual: la Saga lo resolverá.
8. **Dado** un usuario sin `administrador`, **entonces** recibe `403 SIN_PERMISO`.
9. **Dado** dos administradores que resuelven L1 a la vez con la misma `version`, **entonces** uno recibe `200` y el otro `409 CONFLICTO_CONCURRENCIA`.

---

### Casos borde

- Observación vacía o de más de 500 caracteres: `400 DATOS_INVALIDOS`.
- Una labor reintentada que vuelve a quedar en revisión se puede resolver otra vez; `resolucion` guarda solo la última y `idsSagaAnteriores` todas las Sagas.
- Las respuestas tardías de una Saga anterior se registran en esa Saga y no afectan a la labor, que ya apunta a la nueva.

## Requisitos

### Requisitos funcionales

- **RQ-REV-01**: El sistema debe permitir a un `administrador` resolver una labor `PENDIENTE_REVISION` con `decision` (`CONFIRMAR` / `RECHAZAR` / `REINTENTAR`), `observacion` (obligatoria, de 1 a 500 caracteres) y la `version` leída.
- **RQ-REV-02**: Decisiones permitidas según la Saga actual de la labor: `COMPENSADA` → `RECHAZAR` o `REINTENTAR`; `REQUIERE_INTERVENCION` → `CONFIRMAR`; `EN_CURSO` o `COMPENSANDO` → `409 SAGA_EN_CURSO`. Cualquier otra combinación → `422 DECISION_NO_PERMITIDA`.
- **RQ-REV-03**: Efectos: `CONFIRMAR` → `CONFIRMADA`; `RECHAZAR` → `RECHAZADA` con motivo `RECHAZADA_EN_REVISION`; `REINTENTAR` → consulta la campaña (si está `FINALIZADA`, `422 CAMPANIA_FINALIZADA`; si no está disponible, sigue), labor `PENDIENTE` y Saga nueva en la misma escritura.
- **RQ-REV-04**: La labor guarda `resolucion` `{ decision, observacion, administrador: { id, nombre }, fecha, motivoAnterior }` e `idsSagaAnteriores`.
- **RQ-REV-05**: La actualización es condicional a `estado = PENDIENTE_REVISION` y a la `version` recibida (README D-07); se audita `RESOLVER_LABOR` con el `sub` del administrador.

### Entidades clave

- **LaborAgricola**: agrega `resolucion` e `idsSagaAnteriores`.
- **DecisionRevision**: `CONFIRMAR` / `RECHAZAR` / `REINTENTAR` (glosario de la constitución v2.8.0).

## Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Decisión desconocida, observación ausente o larga, `version` ausente |
| 404 | `LABOR_NO_ENCONTRADA` | La labor no existe |
| 409 | `SAGA_EN_CURSO` | La Saga todavía no termina |
| 409 | `CONFLICTO_CONCURRENCIA` | La labor cambió desde que se leyó |
| 422 | `LABOR_NO_EN_REVISION` | La labor no está `PENDIENTE_REVISION` |
| 422 | `DECISION_NO_PERMITIDA` | La decisión no corresponde al estado de la Saga |
| 422 | `CAMPANIA_FINALIZADA` | `REINTENTAR` en una campaña finalizada |

## Criterios de éxito

- **CE-REV-01**: Cada fila de RQ-REV-02 tiene un test de integración.
- **CE-REV-02**: Tras `REINTENTAR`, la labor termina igual que una labor nueva con los mismos datos (`CONFIRMADA` con participantes sanos).
- **CE-REV-03**: Toda resolución tiene su auditoría.

## Supuestos

- El administrador encuentra las labores a resolver con `GET /labores?estado=PENDIENTE_REVISION` y ve el detalle de la Saga con `GET /sagas/{id}`.

## Aclaraciones

- **AC-01** — Resuelta (constitución v2.8.0): la tabla de permisos incluye `REINTENTAR` en "Resolver labores `PENDIENTE_REVISION`".

## Fuera de alcance

- Corregir los datos de la labor (cantidades, campaña) antes de reintentar: se registra una labor nueva.
- Restaurar insumos o anular costos a mano desde este servicio.

---

# 2. Plan

Reutiliza `RepositorioLabor`, `IniciarSaga` y `PasarelaCampania`. No crea tablas.

## 2.1 Endpoint

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /labores/{id}/resolucion` | `administrador` | `200` + labor | 400, 401, 403, 404, 409, 422 |

```json
{ "decision": "REINTENTAR", "observacion": "Gestión estuvo caída el 02/11", "version": 3 }
```

La respuesta de labor agrega:

```json
"resolucion": {
  "decision": "REINTENTAR",
  "observacion": "Gestión estuvo caída el 02/11",
  "administrador": { "id": "sub", "nombre": "Luis Mamani" },
  "fecha": "2026-11-02T16:00:00Z",
  "motivoAnterior": { "codigo": "SIN_RESPUESTA_GESTION", "mensaje": "…", "detalles": [] }
},
"idsSagaAnteriores": ["uuid"]
```

## 2.2 Diseño por capas

| Capa | Archivo | Responsabilidad |
|---|---|---|
| `Domain/FieldTask` | `LaborAgricola.php` (se amplía), `DecisionRevision.php`, `Resolucion.php` | `resolver(decision, observacion, administrador, estadoSaga, ahora)` con RQ-REV-02 y RQ-REV-03 |
| `Application/UseCases/ResolveReview` | `ResolverRevisionCasoUso.php`, `ResolverRevisionEntrada.php` | Lee labor y Saga, consulta la campaña si es `REINTENTAR`, escribe labor (+ Saga nueva) y auditoría, publica `DescontarInsumos` tras el commit |
| `InterfaceAdapters/Http` | `LaborControlador.php` (se amplía), `Requests/ResolverRevisionRequest.php` | |

## 2.3 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `tests/Unit/Domain/FieldTask/ResolucionLaborTest.php` | RQ-REV-02 completo |
| Integración | `tests/Integration/Http/ResolucionLaboresTest.php` | Historia 1 completa, con auditoría (el escenario 9 con `EnParalelo`); `REINTENTAR` con participantes simulados hasta `CONFIRMADA` (CE-REV-02) |

---

# 3. Tareas

- [ ] **T01** — Ampliar `LaborAgricola` con `resolver` y crear `DecisionRevision` y `Resolucion`, con `ResolucionLaborTest.php`.
- [ ] **T02** — Implementar `ResolverRevisionCasoUso` y `POST /labores/{id}/resolucion`. *Hecho cuando:* pasa `ResolucionLaboresTest.php`.
- [ ] **T03** — Documentar el endpoint en `openapi.yaml` y verificar CE-REV-01 a CE-REV-03.
