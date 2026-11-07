# Producción de campaña — `servicio-gestion`

| Campo | Valor |
|---|---|
| Servicio | `servicio-gestion` |
| Archivo | `specs/spec-produccion.md` |
| Estado | Spec aprobada (2026-11-01) · Implementada (2026-11-02) |
| Fecha | 2026-11-01 |
| Constitución | v2.7.0 |
| Trazabilidad | CU-03 (prioridad alta) · RF-05 · RN-03 (dato de entrada) · RNF-05 |
| Depende de | `spec-campanias.md` |


Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Escenarios de usuario y pruebas

### Historia 1 — Registrar la producción obtenida (Prioridad: P1)

Como administrador, quiero registrar cuánto se cosechó en una campaña, para poder calcular su rendimiento por hectárea y cerrarla.

**Por qué esta prioridad:** sin producción no hay rendimiento ni indicadores (RN-03), y la campaña no se puede finalizar (`spec-campanias.md`, AC-01).

**Prueba independiente:** sobre una campaña en curso, se registra la producción y se consulta.

**Escenarios de aceptación:**

1. **Dado** una campaña `EN_CURSO`, **cuando** el administrador registra 76.500 kg cosechados el 2027-03-20, **entonces** la producción queda registrada con la fecha y el usuario.
2. **Dado** una campaña `PLANIFICADA`, **cuando** se registra producción, **entonces** se rechaza con `422 CAMPANIA_NO_EN_CURSO`.
3. **Dado** una campaña `FINALIZADA`, **cuando** se registra o corrige producción, **entonces** se rechaza con `422 CAMPANIA_FINALIZADA`.
4. **Dado** una cantidad negativa, **cuando** se registra, **entonces** se rechaza con `422 PRODUCCION_INVALIDA`.
5. **Dado** una pérdida total de la cosecha, **cuando** se registra cantidad 0, **entonces** se acepta (ver Supuestos).

---

### Historia 2 — Corregir la producción antes de finalizar (Prioridad: P2)

Como administrador, quiero corregir la producción registrada mientras la campaña siga en curso, por ejemplo cuando llega el peso final de la balanza.

**Por qué esta prioridad:** corrige errores sin bloquear el flujo principal.

**Prueba independiente:** se registra una producción, se corrige y se verifica el valor final y la auditoría.

**Escenarios de aceptación:**

1. **Dado** una producción de 76.500 kg en una campaña `EN_CURSO`, **cuando** se registra 77.120 kg, **entonces** la producción pasa a 77.120 kg y queda su registro de auditoría.

---

### Historia 3 — Consultar la producción (Prioridad: P1)

Como administrador o gerente, quiero ver la producción de una campaña.

**Escenarios de aceptación:**

1. **Dado** una campaña con producción, **cuando** se consulta, **entonces** se devuelve cantidad, unidad, fecha de cosecha, observaciones y fecha de registro.
2. **Dado** una campaña sin producción, **cuando** se consulta, **entonces** se responde `404 PRODUCCION_NO_REGISTRADA`.

---

### Casos borde

- Fecha de cosecha anterior al día de inicio real de la campaña (`fechaInicioEjecucion`, en UTC) o posterior a hoy: `422 FECHA_COSECHA_INVALIDA`.
- Cantidad con más de 2 decimales: `400 DATOS_INVALIDOS`.
- Registro de producción simultáneo con la finalización: o se registra antes, o se rechaza con `CAMPANIA_FINALIZADA`.

## Requisitos

### Requisitos funcionales

- **RQ-PRO-01**: El sistema debe permitir registrar la producción de una campaña `EN_CURSO` con:
  - `cantidad`: obligatoria, mayor o igual a 0, hasta 2 decimales, en kilogramos, la unidad del cultivo de la campaña (README, D-03; `spec-cultivos.md`).
  - `fechaCosecha`: obligatoria, fecha sin hora, entre el día de `fechaInicioEjecucion` de la campaña (en UTC) y la fecha actual.
  - `observaciones`: opcional, hasta 500 caracteres.
- **RQ-PRO-02**: Una campaña tiene como máximo una producción. Registrar de nuevo reemplaza la anterior (corrección), solo mientras la campaña esté `EN_CURSO`.
- **RQ-PRO-03**: La producción es parte del agregado `Campania`; las reglas de estado se validan en él.
- **RQ-PRO-04**: El sistema debe devolver la producción de una campaña, o `404 PRODUCCION_NO_REGISTRADA`.
- **RQ-PRO-05**: Todo registro y corrección genera un registro de auditoría (usuario, acción, fecha y entidad).

### Entidades clave

- **ProduccionCampania** (dentro del agregado `Campania`): `cantidad`, `unidad`, `fechaCosecha`, `observaciones`, `fechaRegistro`, `usuarioRegistro`.

## Permisos

| Operación | Roles |
|---|---|
| Registrar y corregir | `administrador` |
| Consultar | `administrador`, `gerencia`, cuentas de servicio autorizadas |

## Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Formato incorrecto o decimales excedidos |
| 404 | `CAMPANIA_NO_ENCONTRADA` | La campaña no existe |
| 404 | `PRODUCCION_NO_REGISTRADA` | La campaña no tiene producción |
| 409 | `CONFLICTO_CONCURRENCIA` | La campaña cambió desde que se leyó |
| 422 | `PRODUCCION_INVALIDA` | Cantidad negativa |
| 422 | `FECHA_COSECHA_INVALIDA` | Fecha fuera del rango permitido |
| 422 | `CAMPANIA_NO_EN_CURSO` | La campaña está `PLANIFICADA` |
| 422 | `CAMPANIA_FINALIZADA` | La campaña está finalizada |

## Criterios de éxito

- **CE-PRO-01**: Toda campaña `FINALIZADA` tiene exactamente una producción registrada.
- **CE-PRO-02**: La producción de una campaña finalizada no cambia nunca (test de integración).
- **CE-PRO-03**: Registro y consulta responden en menos de 3 s (RNF-05).

## Supuestos

- La producción se registra en `EN_CURSO` y es requisito para finalizar (decisión de `spec-campanias.md`, AC-01).
- Se acepta producción 0 para representar una pérdida total. Es un dato real, distinto de "sin producción registrada": el rendimiento resultante es 0, no `null`.
- Se registra la producción total de la campaña, no por cosechas parciales.
- RF-05 dice "al finalizar una campaña": se cumple registrándola en `EN_CURSO`, justo antes de finalizar, porque una campaña `FINALIZADA` no admite cambios (`spec-campanias.md`, AC-01).

## Aclaraciones

Ninguna. D-03 (kilogramos) y `spec-campanias.md`, AC-01 están resueltas.

## Fuera de alcance

- Cosechas parciales o por lotes.
- Calidad, humedad o clasificación del grano.
- Ventas y precio de la producción (fuera del alcance del sistema).


---

# 2. Plan

Reutiliza la base del servicio (Fase 0 de `spec-parcelas.md`) y el agregado `Campania` de `spec-campanias.md`. Criterio: lo mínimo que cumple la spec.

## 2.1 Endpoints

Prefijo: `/api/gestion/v1`.

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `PUT /campanias/{id}/produccion` | `administrador` | `200` + producción (registra o corrige) | 400, 401, 403, 404 `CAMPANIA_NO_ENCONTRADA`, 409 `CONFLICTO_CONCURRENCIA`, 422 `PRODUCCION_INVALIDA`, `FECHA_COSECHA_INVALIDA`, `CAMPANIA_NO_EN_CURSO` o `CAMPANIA_FINALIZADA` |
| `GET /campanias/{id}/produccion` | `administrador`, `gerencia`, `lectura_gestion` | `200` + producción | 401, 403, 404 `CAMPANIA_NO_ENCONTRADA` o `PRODUCCION_NO_REGISTRADA` |

**Solicitud:**

```json
{ "cantidad": "76500.00", "fechaCosecha": "2027-03-20", "observaciones": "Peso de balanza" }
```

**Respuesta:** `cantidad`, `unidad` (`KILOGRAMO`), `fechaCosecha`, `observaciones` y `fechaRegistro`.

**Validaciones del DTO** (`400 DATOS_INVALIDOS`): `cantidad` `@NotNull @Digits(integer = 12, fraction = 2)`; `fechaCosecha` `@NotNull`; `observaciones` `@Size(max = 500)`. La cantidad negativa la rechaza el dominio con `422 PRODUCCION_INVALIDA`; 0 se acepta.

**Concurrencia:** el cliente no envía versión; la protege el `@Version` interno de la campaña.

## 2.2 Modelo de datos

**`V6__crear_produccion_campania.sql`**

```sql
CREATE TABLE produccion_campania (
    id_campania       UUID          PRIMARY KEY REFERENCES campania (id),
    cantidad          NUMERIC(14,2) NOT NULL CHECK (cantidad >= 0),
    unidad            VARCHAR(20)   NOT NULL CHECK (unidad IN ('KILOGRAMO')),
    fecha_cosecha     DATE          NOT NULL,
    observaciones     VARCHAR(500),
    fecha_registro    TIMESTAMPTZ   NOT NULL,
    usuario_registro  VARCHAR(100)  NOT NULL
);
```

La clave primaria `id_campania` garantiza una sola producción por campaña.

## 2.3 Diseño por capas

| Capa | Clase | Responsabilidad |
|---|---|---|
| `domain/campaign` | `ProduccionCampania` | Valida cantidad ≥ 0 y fecha de cosecha entre el inicio real de la campaña (`fechaInicioEjecucion`) y hoy |
| `domain/campaign` | `Campania` (se amplía) | `registrarProduccion(...)`: solo en `EN_CURSO`; reemplaza la anterior; actualiza `fechaActualizacion`. `tieneProduccion()` habilita la finalización |
| `application/campaign` | `RegistrarProduccionCasoUso` | Carga la campaña (404) y la unidad de su cultivo, toma el `sub` del token como usuario, delega, guarda y audita `CREAR` o `MODIFICAR` sobre `PRODUCCION_CAMPANIA` |
| `application/campaign` | `ConsultarProduccionCasoUso` | Devuelve la producción o `PRODUCCION_NO_REGISTRADA` |
| `infrastructure/persistence` | `ProduccionCampaniaEntidad`, `ProduccionCampaniaSpringData` | Persistencia dentro del agregado: la guarda y la carga `RepositorioCampaniaJpa`, sin relación JPA, porque una relación 1 a 1 por clave compartida no se carga de forma diferida y penalizaría el listado de campañas |
| `interfaces/rest` | `ProduccionControlador` + DTO | Traduce HTTP |

**Resumen de la campaña:** `ConsultarCampaniaCasoUso` pasa a devolver la producción real en `resumen.produccion`.

## 2.4 Tests

| Tipo | Clase | Qué verifica |
|---|---|---|
| Unitario | `ProduccionCampaniaTest` | Cantidad negativa, cantidad 0 aceptada, fechas fuera de rango |
| Unitario | `CampaniaProduccionTest` | Registro solo en `EN_CURSO`, corrección, finalización habilitada con producción |
| Integración | `ProduccionControladorIT` | Escenarios de las historias 1 a 3 y auditoría |
| Integración | `FinalizacionCampaniaIT` | Escenario 2 de la historia 2 de `spec-campanias.md`: con producción, `EN_CURSO → FINALIZADA` funciona; después, registrar o corregir producción responde `CAMPANIA_FINALIZADA` (CE-PRO-01 y CE-PRO-02) |

# 3. Tareas

- [x] **T01** — Crear `ProduccionCampania` y ampliar `Campania`, con `ProduccionCampaniaTest` y `CampaniaProduccionTest`.
- [x] **T02** — Crear `V6__crear_produccion_campania.sql` y ampliar la persistencia del agregado.
- [x] **T03** — Implementar `PUT /campanias/{id}/produccion`. *Hecho cuando:* pasan los escenarios de las historias 1 y 2.
- [x] **T04** — Implementar `GET /campanias/{id}/produccion`. *Hecho cuando:* pasan los escenarios de la historia 3.
- [x] **T05** — Completar `resumen.produccion` en el detalle de campaña y escribir `FinalizacionCampaniaIT`.
- [x] **T06** — Documentar los errores en OpenAPI y verificar: `mvn verify` en verde, criterios CE-PRO-01 a CE-PRO-03 cubiertos.
