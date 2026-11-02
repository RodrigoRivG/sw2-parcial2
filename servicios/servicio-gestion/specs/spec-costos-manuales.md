# Costos manuales de campaña — `servicio-gestion`

| Campo | Valor |
|---|---|
| Servicio | `servicio-gestion` |
| Archivo | `specs/spec-costos-manuales.md` |
| Estado | Spec aprobada (2026-11-01) · Plan y tareas en borrador |
| Fecha | 2026-11-01 |
| Constitución | v2.7.0 |
| Trazabilidad | CU-04 (prioridad media, actor Administrador) · RF-04 · RN-15, RN-16 · RNF-05 |
| Depende de | `spec-campanias.md` |


Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Escenarios de usuario y pruebas

### Historia 1 — Registrar un costo manual (Prioridad: P1)

Como administrador, quiero registrar los costos de una campaña que no provienen de insumos del inventario (mano de obra, maquinaria, otros), para conocer su costo total.

**Por qué esta prioridad:** sin costos no hay costo por hectárea ni indicadores (RN-03).

**Prueba independiente:** sobre una campaña en curso, se registra un costo y se verifica en el listado de costos y en el costo total.

**Escenarios de aceptación:**

1. **Dado** una campaña `EN_CURSO`, **cuando** el administrador registra un costo de categoría `MANO_DE_OBRA` por Bs 1.500,00 con descripción "Cosecha manual", **entonces** el costo se guarda con origen `MANUAL` y el costo total de la campaña aumenta en 1.500,00.
2. **Dado** una campaña `PLANIFICADA`, **cuando** se registra un costo de `MAQUINARIA`, **entonces** se acepta.
3. **Dado** una campaña `FINALIZADA`, **cuando** se registra un costo, **entonces** se rechaza con `422 CAMPANIA_FINALIZADA`.
4. **Dado** un monto 0 o negativo, **cuando** se registra el costo, **entonces** se rechaza con `422 MONTO_INVALIDO`.
5. **Dado** un usuario con rol `gerencia`, **cuando** intenta registrar un costo, **entonces** se rechaza con `403 SIN_PERMISO`.

---

### Historia 2 — Consultar los costos de una campaña (Prioridad: P1)

Como administrador o gerente, quiero ver todos los costos de una campaña, manuales y de la Saga, con su categoría y origen, para entender en qué se gastó.

**Por qué esta prioridad:** respalda el costo total y los indicadores.

**Prueba independiente:** con costos de ambos orígenes, se listan y se filtran.

**Escenarios de aceptación:**

1. **Dado** una campaña con costos manuales y costos de la Saga, **cuando** se listan sus costos, **entonces** se devuelven todos, ordenados por fecha descendente, cada uno con `origen` (`MANUAL` o `SAGA`) y, si es de la Saga, con `idLabor`.
2. **Dado** el listado, **cuando** se filtra por `categoria = INSUMO`, **entonces** solo se devuelven los costos de esa categoría.
3. **Dado** el listado, **entonces** la respuesta incluye el total general y el subtotal por categoría.

---

### Historia 3 — Corregir o quitar un costo manual (Prioridad: P2)

Como administrador, quiero corregir o quitar un costo manual cargado por error mientras la campaña no esté finalizada.

**Por qué esta prioridad:** corrige errores; no bloquea el flujo principal.

**Prueba independiente:** se modifica y se elimina un costo manual; se verifica que los costos de la Saga no se pueden tocar.

**Escenarios de aceptación:**

1. **Dado** un costo manual en una campaña `EN_CURSO`, **cuando** se corrige su monto, **entonces** se guarda el cambio y queda su registro de auditoría.
2. **Dado** un costo manual en una campaña `EN_CURSO`, **cuando** se elimina, **entonces** deja de contar en el costo total y la eliminación queda auditada.
3. **Dado** un costo con origen `SAGA`, **cuando** se intenta modificar o eliminar, **entonces** se rechaza con `422 COSTO_NO_EDITABLE`.
4. **Dado** cualquier costo de una campaña `FINALIZADA`, **cuando** se intenta modificar o eliminar, **entonces** se rechaza con `422 CAMPANIA_FINALIZADA`.

---

### Casos borde

- Monto con más de 2 decimales: `400 DATOS_INVALIDOS`; no se redondea en silencio.
- Fecha del costo posterior a hoy: `422 FECHA_COSTO_INVALIDA`.
- Categoría inexistente en `CategoriaCosto`: `400 DATOS_INVALIDOS`.
- Costo de otra campaña modificado o eliminado con un `idCampania` distinto en la ruta: `404 COSTO_NO_ENCONTRADO`.
- Registro de un costo manual al mismo tiempo que se finaliza la campaña: o queda registrado antes de finalizar, o se rechaza con `CAMPANIA_FINALIZADA`.

## Requisitos

### Requisitos funcionales

- **RQ-COS-01**: El sistema debe permitir registrar un costo manual en una campaña `PLANIFICADA` o `EN_CURSO`, con:
  - `categoria`: obligatoria, valor de `CategoriaCosto` (ver AC-01).
  - `monto`: obligatorio, mayor a 0, hasta 2 decimales, en bolivianos (`BOB`, README D-01).
  - `fecha`: obligatoria, fecha sin hora, no posterior a la fecha actual.
  - `descripcion`: obligatoria, de 1 a 300 caracteres.
- **RQ-COS-02**: Un costo manual se guarda con `origen = MANUAL`.
- **RQ-COS-03**: La validación de estado se hace en el agregado `Campania`: una campaña `FINALIZADA` responde `422 CAMPANIA_FINALIZADA`.
- **RQ-COS-04**: El sistema debe listar los costos de una campaña (manuales y de la Saga), ordenados por fecha descendente, con filtro opcional por `categoria` y `origen`, e incluir total general y subtotal por categoría.
- **RQ-COS-05**: El sistema debe permitir modificar `categoria`, `monto`, `fecha` y `descripcion` de un costo manual, y eliminarlo, mientras la campaña no esté `FINALIZADA`.
- **RQ-COS-06**: Los costos con `origen = SAGA` no se modifican ni se eliminan por la API; el intento responde `422 COSTO_NO_EDITABLE`.
- **RQ-COS-07**: Toda creación, modificación y eliminación genera un registro de auditoría (usuario, acción, fecha y entidad).
- **RQ-COS-08**: Los cálculos de totales se hacen con aritmética decimal exacta; nunca con punto flotante.
- **RQ-COS-09**: Los costos de la Saga anulados por compensación (`spec-costo-saga.md`) no aparecen en el listado ni suman en totales; se conservan para auditoría e idempotencia.

### Entidades clave

- **CostoCampania** (dentro del agregado `Campania`): `id` (UUID), `categoria`, `monto`, `fecha`, `descripcion`, `origen` (`MANUAL` / `SAGA`), `idSaga` y `idLabor` (solo origen `SAGA`, `spec-costo-saga.md`), `anulado` y `fechaAnulacion` (solo origen `SAGA`), `fechaRegistro`.
- **CategoriaCosto**: `INSUMO` / `MANO_DE_OBRA` / `MAQUINARIA` / `OTRO`.
- **OrigenCosto**: `MANUAL` / `SAGA` (glosario de la constitución v2.1.0).

## Permisos

| Operación | Roles |
|---|---|
| Registrar, modificar y eliminar costos manuales | `administrador` |
| Listar costos | `administrador`, `gerencia`, cuentas de servicio autorizadas |

## Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Formato incorrecto, decimales excedidos, categoría inexistente |
| 404 | `CAMPANIA_NO_ENCONTRADA` | La campaña no existe |
| 404 | `COSTO_NO_ENCONTRADO` | El costo no existe en esa campaña |
| 409 | `CONFLICTO_CONCURRENCIA` | La campaña cambió desde que se leyó |
| 422 | `MONTO_INVALIDO` | Monto menor o igual a 0 |
| 422 | `FECHA_COSTO_INVALIDA` | Fecha posterior a hoy |
| 422 | `CAMPANIA_FINALIZADA` | La campaña está finalizada |
| 422 | `COSTO_NO_EDITABLE` | Se intenta cambiar un costo de la Saga |

## Criterios de éxito

- **CE-COS-01**: El costo total de una campaña coincide al centavo con la suma de sus costos, en todos los tests.
- **CE-COS-02**: Ningún costo de origen `SAGA` puede alterarse por la API (test de integración).
- **CE-COS-03**: El listado de costos de una campaña con 1.000 costos responde en menos de 3 s (RNF-05).

## Supuestos

- Un costo puede tener fecha anterior a `fechaInicio` de la campaña (gastos de preparación).
- La eliminación de un costo manual es física, con registro de auditoría. La prohibición de borrado físico de la constitución aplica a campañas, no a costos manuales individuales.

## Aclaraciones

- **AC-01** — Resuelta (2026-11-01): se permiten costos manuales de categoría `INSUMO` para insumos comprados fuera del inventario; la descripción obligatoria debe indicarlo.
- **AC-02** — Resuelta (2026-11-01): los costos manuales se eliminan físicamente, con su registro de auditoría.

## Fuera de alcance

- Costos estimados o presupuestados.
- Proveedores y comprobantes (fuera del alcance del sistema).
- Prorrateo de costos entre campañas.


---

# 2. Plan

Reutiliza la base del servicio (Fase 0 de `spec-parcelas.md`) y el agregado `Campania` de `spec-campanias.md`. Criterio: lo mínimo que cumple la spec.

## 2.1 Endpoints

Prefijo: `/api/gestion/v1`.

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /campanias/{id}/costos` | `administrador` | `201` + `Location` + costo | 400, 401, 403, 404 `CAMPANIA_NO_ENCONTRADA`, 409 `CONFLICTO_CONCURRENCIA`, 422 `MONTO_INVALIDO`, `FECHA_COSTO_INVALIDA` o `CAMPANIA_FINALIZADA` |
| `GET /campanias/{id}/costos?categoria=&origen=&pagina=&tamanio=` | `administrador`, `gerencia`, `lectura_gestion` | `200` + página con totales | 400, 401, 403, 404 |
| `PUT /campanias/{id}/costos/{idCosto}` | `administrador` | `200` + costo | 400, 401, 403, 404 `COSTO_NO_ENCONTRADO`, 409, 422 (los anteriores y `COSTO_NO_EDITABLE`) |
| `DELETE /campanias/{id}/costos/{idCosto}` | `administrador` | `204` | 401, 403, 404, 409, 422 `COSTO_NO_EDITABLE` o `CAMPANIA_FINALIZADA` |

**Solicitud** (creación y modificación):

```json
{
  "categoria": "MANO_DE_OBRA",
  "monto": "1500.00",
  "fecha": "2026-12-10",
  "descripcion": "Cosecha manual"
}
```

**Respuesta de costo:** `id`, `categoria`, `monto`, `fecha`, `descripcion`, `origen`, `idLabor` (solo origen `SAGA`) y `fechaRegistro`.

**Respuesta del listado:** la página común más los totales de la campaña, calculados sobre todos sus costos vigentes, sin importar los filtros:

```json
{
  "items": [ ],
  "pagina": 0,
  "tamanio": 20,
  "total": 3,
  "costoTotal": "2320.50",
  "subtotalesPorCategoria": {
    "INSUMO": "820.50", "MANO_DE_OBRA": "1500.00", "MAQUINARIA": "0.00", "OTRO": "0.00"
  }
}
```

**Validaciones del DTO** (`400 DATOS_INVALIDOS`): `categoria` `@NotNull` y valor de `CategoriaCosto`; `monto` `@NotNull @Digits(integer = 12, fraction = 2)`; `fecha` `@NotNull`; `descripcion` `@NotBlank @Size(max = 300)`. El monto 0 o negativo lo rechaza el dominio con `422 MONTO_INVALIDO`.

**Concurrencia:** el cliente no envía versión. La protege el `@Version` interno de la campaña: cualquier cambio de costos actualiza la campaña, y dos cambios simultáneos terminan con uno en `409 CONFLICTO_CONCURRENCIA`.

## 2.2 Modelo de datos

**`V5__crear_costo_campania.sql`**

```sql
CREATE TABLE costo_campania (
    id               UUID PRIMARY KEY,
    id_campania      UUID          NOT NULL REFERENCES campania (id),
    categoria        VARCHAR(20)   NOT NULL CHECK (categoria IN ('INSUMO','MANO_DE_OBRA','MAQUINARIA','OTRO')),
    monto            NUMERIC(14,2) NOT NULL CHECK (monto > 0),
    fecha            DATE          NOT NULL,
    descripcion      VARCHAR(300)  NOT NULL,
    origen           VARCHAR(10)   NOT NULL CHECK (origen IN ('MANUAL','SAGA')),
    id_saga          UUID          UNIQUE,
    id_labor         UUID,
    anulado          BOOLEAN       NOT NULL DEFAULT FALSE,
    fecha_anulacion  TIMESTAMPTZ,
    fecha_registro   TIMESTAMPTZ   NOT NULL
);
CREATE INDEX ix_costo_campania ON costo_campania (id_campania, fecha DESC);
```

Las columnas `id_saga`, `id_labor`, `anulado` y `fecha_anulacion` se crean aquí para tener un solo esquema de costos; las usa `spec-costo-saga.md`.

## 2.3 Diseño por capas

| Capa | Clase | Responsabilidad |
|---|---|---|
| `domain/campaign` | `CostoCampania` | Entidad del agregado; valida monto > 0 y fecha no futura (recibe la fecha de hoy) |
| `domain/campaign` | `CategoriaCosto`, `OrigenCosto` | Enums del glosario |
| `domain/campaign` | `Campania` (se amplía) | `registrarCostoManual`, `modificarCostoManual`, `eliminarCostoManual`: rechazan si está `FINALIZADA` o si el costo es de la Saga; `costoTotal()` y `subtotalesPorCategoria()` sobre costos no anulados; todas actualizan `fechaActualizacion` |
| `domain/shared` | `Dinero` | Objeto de valor sobre `BigDecimal` con escala 2 |
| `application/campaign` | `RegistrarCostoManualCasoUso`, `ModificarCostoManualCasoUso`, `EliminarCostoManualCasoUso`, `ListarCostosCasoUso` | Cargan la campaña (404), delegan en el agregado, guardan y auditan `CREAR`, `MODIFICAR` o `ELIMINAR` sobre la entidad `COSTO_CAMPANIA`. La fecha de hoy sale de un `java.time.Clock` en UTC |
| `infrastructure/persistence` | `CostoCampaniaEntidad` (+ relación en `CampaniaEntidad`), `MapeadorCampania` (se amplía) | Persistencia de costos dentro del agregado; el listado paginado usa una consulta propia sobre `costo_campania` |
| `interfaces/rest` | `CostoCampaniaControlador` + DTO | Traduce HTTP |

**Resumen de la campaña:** `ConsultarCampaniaCasoUso` pasa a devolver `costoTotal` y `cantidadCostos` reales (actualiza lo dejado en cero en `spec-campanias.md`).

## 2.4 Tests

| Tipo | Clase | Qué verifica |
|---|---|---|
| Unitario | `CostoCampaniaTest` | Monto ≤ 0 y fecha futura rechazados |
| Unitario | `CampaniaCostosTest` | Costos en `PLANIFICADA` y `EN_CURSO`, rechazo en `FINALIZADA`, `COSTO_NO_EDITABLE` en costos de la Saga, totales exactos sin anulados |
| Integración | `CostoCampaniaControladorIT` | Escenarios de las historias 1 a 3, filtros, totales y auditoría |
| Integración | `CostoCampaniaRendimientoIT` | 1.000 costos: listado en menos de 3 s (CE-COS-03) |

Para probar `COSTO_NO_EDITABLE` antes de tener la Saga, el test inserta un costo con origen `SAGA` directamente en la base.

# 3. Tareas

- [x] **T01** — Crear `CostoCampania`, `CategoriaCosto`, `OrigenCosto` y `Dinero`; ampliar `Campania`; con `CostoCampaniaTest` y `CampaniaCostosTest`.
- [x] **T02** — Crear `V5__crear_costo_campania.sql` y ampliar la persistencia del agregado.
- [x] **T03** — Implementar `POST /campanias/{id}/costos`. *Hecho cuando:* pasan los escenarios de la historia 1.
- [x] **T04** — Implementar `GET /campanias/{id}/costos` con totales. *Hecho cuando:* pasan los escenarios de la historia 2.
- [x] **T05** — Implementar `PUT` y `DELETE` de costos. *Hecho cuando:* pasan los escenarios de la historia 3.
- [x] **T06** — Completar `costoTotal` y `cantidadCostos` en el detalle de campaña.
- [x] **T07** — Escribir `CostoCampaniaRendimientoIT` y documentar los errores en OpenAPI.
- [x] **T08** — Verificación final: `mvn verify` en verde y criterios CE-COS-01 a CE-COS-03 cubiertos.
