# Campañas y ciclo de estado — `servicio-gestion`

| Campo | Valor |
|---|---|
| Servicio | `servicio-gestion` |
| Archivo | `specs/spec-campanias.md` |
| Estado | Spec aprobada (2026-11-01) · Plan y tareas en borrador |
| Fecha | 2026-11-01 |
| Constitución | v2.7.0 |
| Trazabilidad | CU-03 (prioridad alta) · RF-03 · RN-01, RN-02, RN-06, RN-15, RN-16 · RNF-05 |
| Depende de | `spec-parcelas.md`, `spec-cultivos.md` |


Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Escenarios de usuario y pruebas

### Historia 1 — Crear una campaña (Prioridad: P1)

Como administrador, quiero crear una campaña que combine una parcela, un cultivo y un periodo, para registrar sobre ella costos, labores y producción.

**Por qué esta prioridad:** la campaña es la raíz de costos, producción e indicadores, y la referencia que usan `servicio-operaciones` y `servicio-ia`.

**Prueba independiente:** con una parcela y un cultivo existentes, se crea la campaña y se consulta en estado `PLANIFICADA`.

**Escenarios de aceptación:**

1. **Dado** la parcela "Lote Norte" (25,5 ha) y el cultivo "Soya", **cuando** el administrador crea la campaña "Soya verano 2026-2027" del 2026-11-15 al 2027-03-30, **entonces** se crea en estado `PLANIFICADA`, con `superficieHectareas` = 25,5 tomada de la parcela.
2. **Dado** una fecha de fin igual o anterior a la de inicio, **cuando** se crea la campaña, **entonces** se rechaza con `422 FECHAS_INVALIDAS` (RN-01).
3. **Dado** un `idParcela` inexistente, **cuando** se crea la campaña, **entonces** se rechaza con `404 PARCELA_NO_ENCONTRADA`; lo mismo para el cultivo con `404 CULTIVO_NO_ENCONTRADO`.
4. **Dado** un usuario con rol `gerencia`, **cuando** intenta crear una campaña, **entonces** se rechaza con `403 SIN_PERMISO`.

---

### Historia 2 — Avanzar el estado de una campaña (Prioridad: P1)

Como administrador, quiero marcar una campaña como iniciada y luego como finalizada, para reflejar su avance real y cerrar sus datos.

**Por qué esta prioridad:** el estado gobierna qué se puede registrar (costos, producción, labores) y es lo que consulta `servicio-operaciones` (RN-06).

**Prueba independiente:** se crea una campaña y se la lleva por `PLANIFICADA → EN_CURSO → FINALIZADA`, verificando los rechazos de transiciones inválidas.

**Escenarios de aceptación:**

1. **Dado** una campaña `PLANIFICADA`, **cuando** se cambia a `EN_CURSO`, **entonces** queda `EN_CURSO` y se registra la fecha y el usuario del cambio.
2. **Dado** una campaña `EN_CURSO` con producción registrada, **cuando** se cambia a `FINALIZADA`, **entonces** queda `FINALIZADA`.
3. **Dado** una campaña `EN_CURSO` sin producción registrada, **cuando** se cambia a `FINALIZADA`, **entonces** se rechaza con `422 FINALIZACION_SIN_PRODUCCION` (ver AC-01).
4. **Dado** una campaña `PLANIFICADA`, **cuando** se intenta pasar directo a `FINALIZADA`, **entonces** se rechaza con `422 TRANSICION_ESTADO_INVALIDA`.
5. **Dado** una campaña `EN_CURSO` o `FINALIZADA`, **cuando** se intenta volver a un estado anterior, **entonces** se rechaza con `422 TRANSICION_ESTADO_INVALIDA` (RN-02).
6. **Dado** una campaña `EN_CURSO`, **cuando** se pide el cambio a `EN_CURSO` (mismo estado), **entonces** se rechaza con `422 TRANSICION_ESTADO_INVALIDA`.
7. **Dado** una parcela que ya tiene una campaña `EN_CURSO`, **cuando** se intenta pasar a `EN_CURSO` otra campaña de la misma parcela, **entonces** se rechaza con `409 PARCELA_CON_CAMPANIA_EN_CURSO`.

---

### Historia 3 — Consultar campañas (Prioridad: P1)

Como administrador o gerente, quiero listar las campañas con filtros y ver el detalle de cada una, para seguir la situación de la producción.

**Por qué esta prioridad:** es la vista principal de seguimiento.

**Prueba independiente:** con campañas en distintos estados, se filtran y se consulta el detalle.

**Escenarios de aceptación:**

1. **Dado** campañas en varios estados, **cuando** se filtra por `estado = EN_CURSO`, **entonces** solo se devuelven las que están en curso.
2. **Dado** campañas de varias parcelas y cultivos, **cuando** se filtra por `idParcela` y/o `idCultivo`, **entonces** se devuelven solo las que coinciden.
3. **Dado** una campaña con costos y producción, **cuando** se consulta su detalle, **entonces** incluye sus datos, su estado y un resumen: costo total, cantidad de costos y producción registrada (o `null`).
4. **Dado** un ID inexistente, **cuando** se consulta, **entonces** se responde `404 CAMPANIA_NO_ENCONTRADA`.
5. **Dado** un usuario `tecnico_campo`, **cuando** lista campañas, **entonces** solo recibe las `PLANIFICADA` y `EN_CURSO`; si filtra por `estado = FINALIZADA`, recibe una lista vacía. El detalle de una campaña no finalizada no incluye `resumen`.
6. **Dado** un usuario `tecnico_campo`, **cuando** consulta el detalle de una campaña `FINALIZADA`, **entonces** se responde `403 SIN_PERMISO`.

---

### Historia 4 — Modificar los datos de una campaña (Prioridad: P2)

Como administrador, quiero corregir el nombre, las fechas, la parcela o el cultivo de una campaña mientras no esté finalizada.

**Por qué esta prioridad:** corrige errores de planificación; no bloquea el flujo principal.

**Prueba independiente:** se modifican campañas en cada estado y se verifica qué se permite.

**Escenarios de aceptación:**

1. **Dado** una campaña `PLANIFICADA`, **cuando** se cambia su parcela, **entonces** se acepta y `superficieHectareas` se actualiza con la superficie de la nueva parcela.
2. **Dado** una campaña `EN_CURSO`, **cuando** se cambia su nombre o su fecha de fin, **entonces** se acepta.
3. **Dado** una campaña `EN_CURSO`, **cuando** se intenta cambiar su parcela, su cultivo o su fecha de inicio, **entonces** se rechaza con `422 CAMPO_NO_MODIFICABLE`.
4. **Dado** una campaña `FINALIZADA`, **cuando** se intenta cualquier modificación, **entonces** se rechaza con `422 CAMPANIA_FINALIZADA`.
5. **Dado** cualquier modificación de fechas, **cuando** la fecha de fin queda igual o anterior a la de inicio, **entonces** se rechaza con `422 FECHAS_INVALIDAS`.

---

### Casos borde

- Dos cambios de estado simultáneos sobre la misma campaña: uno se aplica; el otro recibe `409 CONFLICTO_CONCURRENCIA`.
- Un costo de la Saga (`spec-costo-saga.md`) llega al mismo tiempo que la finalización: o el costo queda registrado antes de finalizar, o se rechaza con `CAMPANIA_FINALIZADA`. Nunca queda un costo agregado a una campaña ya finalizada.
- Fechas enviadas con hora (`2026-11-15T00:00:00Z`): `400 DATOS_INVALIDOS`; las fechas de campaña son fechas sin hora.
- La parcela cambia de superficie después de crear la campaña: la campaña conserva su `superficieHectareas` (ver AC-02).
- Estado destino con un valor que no existe en `EstadoCampania`: `400 DATOS_INVALIDOS`.
- Dos campañas de la misma parcela pasan a `EN_CURSO` al mismo tiempo: solo una lo logra; la otra recibe `409 PARCELA_CON_CAMPANIA_EN_CURSO`.

## Requisitos

### Requisitos funcionales

- **RQ-CAM-01**: El sistema debe permitir crear una campaña con:
  - `nombre`: obligatorio, de 1 a 150 caracteres; identifica el periodo productivo (por ejemplo, "Soya verano 2026-2027").
  - `idParcela`: obligatorio, debe existir.
  - `idCultivo`: obligatorio, debe existir.
  - `fechaInicio` y `fechaFin`: obligatorias, fechas sin hora; `fechaFin` estrictamente posterior a `fechaInicio` (RN-01).
- **RQ-CAM-02**: Toda campaña nueva nace en estado `PLANIFICADA`.
- **RQ-CAM-03**: Al crear la campaña, o al cambiar su parcela, se copia la superficie de la parcela en `superficieHectareas` de la campaña. Los indicadores usan esa superficie (ver AC-02).
- **RQ-CAM-04**: Las únicas transiciones válidas son `PLANIFICADA → EN_CURSO` y `EN_CURSO → FINALIZADA`. Cualquier otra responde `422 TRANSICION_ESTADO_INVALIDA` (RN-02).
- **RQ-CAM-05**: Para pasar a `FINALIZADA` la campaña debe tener producción registrada (`spec-produccion.md`); si no, responde `422 FINALIZACION_SIN_PRODUCCION` (ver AC-01).
- **RQ-CAM-06**: Cada cambio de estado guarda la fecha (UTC) en la campaña; el usuario que lo hizo queda en `registro_auditoria` (acción `CAMBIAR_ESTADO`).
- **RQ-CAM-07**: Una campaña `FINALIZADA` no admite modificaciones de datos, costos ni producción; cualquier intento responde `422 CAMPANIA_FINALIZADA`.
- **RQ-CAM-08**: Campos modificables por estado:

  | Campo | `PLANIFICADA` | `EN_CURSO` | `FINALIZADA` |
  |---|---|---|---|
  | `nombre` | Sí | Sí | No |
  | `fechaInicio` | Sí | No | No |
  | `fechaFin` | Sí | Sí | No |
  | `idParcela` | Sí | No | No |
  | `idCultivo` | Sí | No | No |

  Un campo no modificable en el estado actual responde `422 CAMPO_NO_MODIFICABLE`.
- **RQ-CAM-09**: El sistema debe listar campañas paginadas, ordenadas por `fechaInicio` descendente, con filtros opcionales por `estado`, `idParcela`, `idCultivo` y rango de `fechaInicio`. El listado no incluye `resumen`, para no cargar los costos de cada campaña.
- **RQ-CAM-10**: El detalle de una campaña incluye sus datos, su estado, las fechas de cada cambio de estado y un resumen con costo total, cantidad de costos y producción (o `null` si no hay).
- **RQ-CAM-11**: Las modificaciones concurrentes no se pierden en silencio: la que llega con una versión desactualizada recibe `409 CONFLICTO_CONCURRENCIA`.
- **RQ-CAM-12**: Toda creación, modificación y cambio de estado genera un registro de auditoría.
- **RQ-CAM-13**: No se eliminan campañas en esta versión (la constitución prohíbe el borrado físico de campañas con costos; ver Fuera de alcance).
- **RQ-CAM-14**: Una parcela tiene como máximo una campaña `EN_CURSO`. Iniciar una segunda responde `409 PARCELA_CON_CAMPANIA_EN_CURSO`. Se permiten varias campañas `PLANIFICADA` por parcela.
- **RQ-CAM-15**: `tecnico_campo` puede listar y consultar campañas `PLANIFICADA` y `EN_CURSO`, sin el resumen económico. Las campañas `FINALIZADA` no aparecen en sus listados y su detalle responde `403 SIN_PERMISO`.

### Entidades clave

- **Campania** (raíz del agregado): `id` (UUID), `nombre`, `idParcela`, `idCultivo`, `fechaInicio`, `fechaFin`, `superficieHectareas`, `estado`, `fechaInicioEjecucion` (paso a `EN_CURSO`), `fechaFinalizacion` (paso a `FINALIZADA`), `version`. Contiene sus `CostoCampania` (`spec-costos-manuales.md`) y su producción (`spec-produccion.md`).
- **EstadoCampania**: `PLANIFICADA` / `EN_CURSO` / `FINALIZADA`.

## Permisos

| Operación | Roles |
|---|---|
| Crear, modificar y cambiar estado | `administrador` |
| Listar y ver detalle | `administrador`, `gerencia`, cuentas de servicio autorizadas |
| Listar y ver detalle de campañas no finalizadas, sin datos económicos | `tecnico_campo` |

## Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Formato incorrecto, fechas con hora, estado inexistente |
| 404 | `CAMPANIA_NO_ENCONTRADA` | El ID de campaña no existe |
| 404 | `PARCELA_NO_ENCONTRADA` | La parcela indicada no existe |
| 404 | `CULTIVO_NO_ENCONTRADO` | El cultivo indicado no existe |
| 409 | `CONFLICTO_CONCURRENCIA` | La campaña cambió desde que se leyó |
| 409 | `PARCELA_CON_CAMPANIA_EN_CURSO` | La parcela ya tiene otra campaña en curso |
| 422 | `FECHAS_INVALIDAS` | Fin igual o anterior al inicio |
| 422 | `TRANSICION_ESTADO_INVALIDA` | Transición no permitida |
| 422 | `FINALIZACION_SIN_PRODUCCION` | Se intenta finalizar sin producción |
| 422 | `CAMPO_NO_MODIFICABLE` | Campo bloqueado en el estado actual |
| 422 | `CAMPANIA_FINALIZADA` | Se intenta modificar una campaña finalizada |

## Criterios de éxito

- **CE-CAM-01**: El 100 % de las transiciones fuera de `PLANIFICADA → EN_CURSO → FINALIZADA` se rechazan (cubierto por tests unitarios del agregado).
- **CE-CAM-02**: Ninguna campaña finalizada acumula costos, producción ni cambios después de la fecha de finalización, incluso con solicitudes y mensajes concurrentes (test de concurrencia).
- **CE-CAM-03**: Listado con filtros y detalle responden en menos de 3 s con al menos 5.000 campañas (RNF-05).
- **CE-CAM-04**: Los indicadores de una campaña no cambian cuando se modifica la superficie de su parcela.
- **CE-CAM-05**: Nunca existen dos campañas `EN_CURSO` en la misma parcela, incluso con solicitudes concurrentes.

## Supuestos

- `fechaInicio` y `fechaFin` son fechas planificadas. Las fechas reales de inicio y cierre quedan registradas en los cambios de estado.
- Se pueden registrar costos en una campaña `PLANIFICADA` (gastos previos a la siembra), no solo en `EN_CURSO` (ver `spec-costos-manuales.md`).

## Aclaraciones

- **AC-01** — Resuelta (2026-11-01): la producción se registra (y se puede corregir) en `EN_CURSO`, y finalizar exige tenerla registrada.
- **AC-02** — Resuelta (2026-11-01): la campaña copia la superficie de la parcela al crearse o al cambiar de parcela (RQ-CAM-03).
- **AC-03** — Resuelta (2026-11-01): como máximo una campaña `EN_CURSO` por parcela (RQ-CAM-14).

## Fuera de alcance

- Eliminación o anulación de campañas.
- Reapertura de campañas finalizadas.
- Comparación compleja entre campañas (fuera del alcance del sistema).


---

# 2. Plan

Reutiliza la base del servicio (Fase 0 de `spec-parcelas.md`). Criterio: lo mínimo que cumple la spec.

## 2.1 Endpoints

Prefijo: `/api/gestion/v1`.

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /campanias` | `administrador` | `201` + `Location` + campaña | 400, 401, 403, 404 `PARCELA_NO_ENCONTRADA` o `CULTIVO_NO_ENCONTRADO`, 422 `FECHAS_INVALIDAS` |
| `GET /campanias?estado=&idParcela=&idCultivo=&fechaInicioDesde=&fechaInicioHasta=&pagina=&tamanio=` | `administrador`, `gerencia`, `lectura_gestion`, `tecnico_campo` (vista reducida) | `200` + página | 400, 401, 403 |
| `GET /campanias/{id}` | Igual que el listado | `200` + campaña | 401, 403, 404 `CAMPANIA_NO_ENCONTRADA` |
| `PUT /campanias/{id}` | `administrador` | `200` + campaña | 400, 401, 403, 404, 409 `CONFLICTO_CONCURRENCIA`, 422 `FECHAS_INVALIDAS`, `CAMPO_NO_MODIFICABLE` o `CAMPANIA_FINALIZADA` |
| `PUT /campanias/{id}/estado` | `administrador` | `200` + campaña | 400, 401, 403, 404, 409 `CONFLICTO_CONCURRENCIA` o `PARCELA_CON_CAMPANIA_EN_CURSO`, 422 `TRANSICION_ESTADO_INVALIDA` o `FINALIZACION_SIN_PRODUCCION` |

`GET /campanias/{id}/estado` (lectura para integración) se define en `spec-consultas-integracion.md`; comparte la ruta con el cambio de estado pero con otro método.

**Creación:**

```json
{
  "nombre": "Soya verano 2026-2027",
  "idParcela": "uuid",
  "idCultivo": "uuid",
  "fechaInicio": "2026-11-15",
  "fechaFin": "2027-03-30"
}
```

**Modificación de datos:** los mismos campos más `version`. **Cambio de estado:** `{ "estadoDestino": "EN_CURSO", "version": 3 }`.

**Detalle completo** (administrador, gerencia y cuentas de servicio; cada elemento del listado tiene los mismos campos, sin `resumen`):

```json
{
  "id": "uuid",
  "nombre": "Soya verano 2026-2027",
  "idParcela": "uuid",
  "idCultivo": "uuid",
  "fechaInicio": "2026-11-15",
  "fechaFin": "2027-03-30",
  "superficieHectareas": "25.5000",
  "estado": "EN_CURSO",
  "fechaInicioEjecucion": "2026-11-16T12:00:00Z",
  "fechaFinalizacion": null,
  "resumen": { "costoTotal": "0.00", "cantidadCostos": 0, "produccion": null },
  "version": 1,
  "fechaCreacion": "2026-11-02T14:00:00Z",
  "fechaActualizacion": "2026-11-16T12:00:00Z"
}
```

**Elementos del listado y vista reducida para `tecnico_campo`** (`CampaniaSinResumenRespuesta`): igual pero sin `resumen`. Reglas:

- Si el usuario solo tiene `tecnico_campo`, el listado agrega siempre el filtro `estado IN (PLANIFICADA, EN_CURSO)` (combinado con `estado = FINALIZADA` da una lista vacía) y el detalle de una campaña `FINALIZADA` responde `403 SIN_PERMISO`.
- Si además tiene `administrador` o `gerencia`, recibe la vista completa.

**Validaciones del DTO** (`400 DATOS_INVALIDOS`): `nombre` `@NotBlank @Size(max = 150)`; `idParcela`, `idCultivo`, `fechaInicio`, `fechaFin` `@NotNull`; las fechas como `LocalDate` (una fecha con hora falla al convertir); `estadoDestino` `@NotNull` y valor de `EstadoCampania`; `version` `@NotNull`.

## 2.2 Modelo de datos

**`V4__crear_campania.sql`**

```sql
CREATE TABLE campania (
    id                      UUID PRIMARY KEY,
    nombre                  VARCHAR(150)  NOT NULL,
    id_parcela              UUID          NOT NULL REFERENCES parcela (id),
    id_cultivo              UUID          NOT NULL REFERENCES cultivo (id),
    fecha_inicio            DATE          NOT NULL,
    fecha_fin               DATE          NOT NULL,
    superficie_hectareas    NUMERIC(12,4) NOT NULL,
    estado                  VARCHAR(20)   NOT NULL CHECK (estado IN ('PLANIFICADA','EN_CURSO','FINALIZADA')),
    fecha_inicio_ejecucion  TIMESTAMPTZ,
    fecha_finalizacion      TIMESTAMPTZ,
    version                 BIGINT        NOT NULL,
    fecha_creacion          TIMESTAMPTZ   NOT NULL,
    fecha_actualizacion     TIMESTAMPTZ   NOT NULL,
    CHECK (fecha_fin > fecha_inicio)
);
CREATE UNIQUE INDEX ux_campania_parcela_en_curso ON campania (id_parcela) WHERE estado = 'EN_CURSO';
CREATE INDEX ix_campania_filtros ON campania (estado, id_parcela, id_cultivo);
```

- El caso de uso valida que la parcela no tenga otra campaña `EN_CURSO`, y el índice único parcial lo garantiza también con solicitudes simultáneas.
- Las claves foráneas son una barrera de integridad dentro de la misma base; el dominio sigue referenciando a parcela y cultivo solo por ID.

## 2.3 Diseño por capas

| Capa | Clase | Responsabilidad |
|---|---|---|
| `domain/campaign` | `Campania` | Raíz del agregado. `crear(...)` valida fechas y copia la superficie; `actualizarDatos(...)` aplica la tabla de RQ-CAM-08; `cambiarEstado(destino, ahora)` valida la secuencia, exige producción para finalizar y guarda las fechas de ejecución y finalización. Contiene la lista de `CostoCampania` y la `ProduccionCampania` (vacías hasta implementar `spec-costos-manuales.md` y `spec-produccion.md`) |
| `domain/campaign` | `EstadoCampania` | Enum de la constitución |
| `domain/campaign` | `RepositorioCampania` | Puerto: `guardar`, `buscarPorId`, `listar(filtros, pagina, tamanio)`, `existeEnCursoEnParcela(idParcela)` |
| `application/campaign` | `CrearCampaniaCasoUso` | Verifica que existan parcela (404) y cultivo (404), toma la superficie de la parcela, crea, guarda y audita `CREAR` |
| `application/campaign` | `ActualizarCampaniaCasoUso` | Compara `version`; si cambia la parcela, toma su superficie; audita `MODIFICAR` |
| `application/campaign` | `CambiarEstadoCampaniaCasoUso` | Compara `version`; si el destino es `EN_CURSO`, rechaza con `PARCELA_CON_CAMPANIA_EN_CURSO` cuando la parcela ya tiene otra en curso; cambia el estado, guarda y audita `CAMBIAR_ESTADO` |
| `application/campaign` | `ConsultarCampaniaCasoUso`, `ListarCampaniasCasoUso` | Lectura; reciben si el usuario es solo técnico para aplicar el filtro y el 403 |
| `infrastructure/persistence` | `CampaniaEntidad`, `CampaniaSpringData`, `MapeadorCampania`, `RepositorioCampaniaJpa` | Entidad con `@Version`; filtros con `Specification`, que solo agrega las condiciones presentes (PostgreSQL rechaza parámetros nulos sin tipo en JPQL); traduce `ux_campania_parcela_en_curso` a `PARCELA_CON_CAMPANIA_EN_CURSO` |
| `interfaces/rest` | `CampaniaControlador` + DTO | Elige la vista completa o reducida según los roles del token |

**Concurrencia con costos y producción:** toda operación sobre el agregado (registrar un costo, anularlo, registrar producción) actualiza `fechaActualizacion` de la campaña, lo que incrementa su `version`. Así, una finalización concurrente con un costo de la Saga termina en `409` o en `CAMPANIA_FINALIZADA`, nunca en un costo agregado a una campaña finalizada.

**Resumen económico:** en esta funcionalidad `costoTotal` es `"0.00"`, `cantidadCostos` 0 y `produccion` `null`. Se completan al implementar `spec-costos-manuales.md` y `spec-produccion.md`.

## 2.4 Tests

| Tipo | Clase | Qué verifica |
|---|---|---|
| Unitario | `CampaniaTest` | Fechas inválidas, cada transición válida e inválida, mismo estado, finalizar sin producción, tabla de campos modificables por estado, campaña finalizada inmodificable |
| Unitario | `CambiarEstadoCampaniaCasoUsoTest` | Rechazo cuando la parcela ya tiene otra campaña `EN_CURSO` (repositorio simulado a mano) |
| Integración | `CampaniaControladorIT` | Escenarios de las historias 1 a 4, incluidos los 404 de parcela y cultivo, las fechas con hora (`400`) y la auditoría |
| Integración | `CampaniaTecnicoIT` | Listado filtrado, lista vacía con `estado = FINALIZADA`, detalle sin `resumen`, 403 en detalle de finalizada, vista completa si también es `gerencia` |
| Integración | `CampaniaConcurrenciaIT` | Dos cambios de estado con la misma versión → uno `409`; dos campañas de la misma parcela a `EN_CURSO` a la vez → una `409 PARCELA_CON_CAMPANIA_EN_CURSO` |
| Integración | `CampaniaRendimientoIT` | 5.000 campañas: listado con filtros y detalle en menos de 3 s (CE-CAM-03) |

La finalización exitosa y el escenario 2 de la historia 2 se prueban en `spec-produccion.md`, porque requieren producción registrada. La superficie conservada al modificar la parcela (CE-CAM-04) se prueba aquí: se crea la campaña, se modifica la parcela y se comprueba que la campaña mantiene su superficie.

# 3. Tareas

- [x] **T01** — Crear `Campania` y `EstadoCampania`, con `CampaniaTest` (sin producción todavía: finalizar siempre responde `FINALIZACION_SIN_PRODUCCION`).
- [x] **T02** — Crear `V4__crear_campania.sql` y la persistencia, con la traducción del índice parcial.
- [x] **T03** — Implementar `POST /campanias`. *Hecho cuando:* pasan los escenarios de la historia 1.
- [x] **T04** — Implementar los dos `GET` con la vista completa y la reducida. *Hecho cuando:* pasan la historia 3 y `CampaniaTecnicoIT`.
- [x] **T05** — Implementar `PUT /campanias/{id}/estado`. *Hecho cuando:* pasan los escenarios 1 y 3 a 7 de la historia 2.
- [x] **T06** — Implementar `PUT /campanias/{id}`. *Hecho cuando:* pasan los escenarios de la historia 4 y el test de CE-CAM-04.
- [x] **T07** — Escribir `CampaniaConcurrenciaIT` y `CampaniaRendimientoIT`; documentar los errores en OpenAPI.
- [x] **T08** — Verificación final: `mvn verify` en verde y criterios CE-CAM-01 a CE-CAM-05 cubiertos (CE-CAM-02 se completa en `spec-costo-saga.md`).
