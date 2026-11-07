# Cultivos — `servicio-gestion`

| Campo | Valor |
|---|---|
| Servicio | `servicio-gestion` |
| Archivo | `specs/spec-cultivos.md` |
| Estado | Spec aprobada (2026-11-01) · Implementada (2026-11-02) |
| Fecha | 2026-11-01 |
| Constitución | v2.7.0 |
| Trazabilidad | CU-02 (prioridad alta) · RF-02 · RN-15, RN-16 · RNF-05 |
| Depende de | — |


Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Escenarios de usuario y pruebas

### Historia 1 — Registrar un cultivo (Prioridad: P1)

Como administrador, quiero registrar los cultivos que se siembran (por ejemplo, soya variedad X) con su unidad de medida de producción, para asociarlos a las campañas.

**Por qué esta prioridad:** toda campaña necesita un cultivo; sin catálogo no se pueden crear campañas.

**Prueba independiente:** se crea un cultivo y se consulta; funciona como catálogo por sí solo.

**Escenarios de aceptación:**

1. **Dado** un administrador autenticado, **cuando** registra el cultivo "Soya" con variedad "Munasqa" y unidad `KILOGRAMO`, **entonces** se crea con un UUID y se devuelve con sus datos.
2. **Dado** que existe "Soya / Munasqa", **cuando** se registra "soya / munasqa", **entonces** se rechaza con `409 CULTIVO_DUPLICADO`.
3. **Dado** que existe "Soya / Munasqa", **cuando** se registra "Soya" con otra variedad o sin variedad, **entonces** se crea sin conflicto.
4. **Dado** un usuario con rol `gerencia`, **cuando** intenta registrar un cultivo, **entonces** se rechaza con `403 SIN_PERMISO`.
5. **Dado** una unidad distinta de `KILOGRAMO` (por ejemplo, `QUINTAL`) o sin unidad, **cuando** se registra el cultivo, **entonces** se rechaza con `400 DATOS_INVALIDOS`.

---

### Historia 2 — Consultar cultivos (Prioridad: P1)

Como administrador o gerente, quiero ver el catálogo de cultivos, para elegir uno al crear una campaña.

**Por qué esta prioridad:** es el paso previo obligatorio a crear una campaña.

**Prueba independiente:** con cultivos cargados, se listan y se consulta uno por ID.

**Escenarios de aceptación:**

1. **Dado** varios cultivos, **cuando** se pide el listado, **entonces** se devuelven paginados y ordenados por nombre y luego por variedad.
2. **Dado** un ID inexistente, **cuando** se consulta el detalle, **entonces** se responde `404 CULTIVO_NO_ENCONTRADO`.

---

### Historia 3 — Modificar un cultivo (Prioridad: P3)

Como administrador, quiero corregir el nombre, la variedad o la descripción de un cultivo.

**Por qué esta prioridad:** solo corrige errores de carga.

**Prueba independiente:** se modifica un cultivo y se verifica el cambio y su auditoría.

**Escenarios de aceptación:**

1. **Dado** un cultivo "Soja", **cuando** el administrador lo renombra a "Soya", **entonces** el cambio se guarda y las campañas asociadas muestran el nuevo nombre (se referencian por ID).
2. **Dado** un cultivo, **cuando** se le asigna una combinación nombre + variedad ya existente, **entonces** se rechaza con `409 CULTIVO_DUPLICADO`.

---

### Casos borde

- Variedad vacía o solo espacios: se trata como "sin variedad".
- Nombre con espacios al inicio o al final: se recortan antes de validar.
- Creación simultánea del mismo nombre + variedad: solo una tiene éxito; la otra recibe `409 CULTIVO_DUPLICADO`.

## Requisitos

### Requisitos funcionales

- **RQ-CUL-01**: El sistema debe permitir registrar un cultivo con:
  - `nombre`: obligatorio, de 1 a 100 caracteres.
  - `variedad`: opcional, hasta 100 caracteres.
  - `unidadMedida`: obligatoria, valor de `UnidadProduccion`. En esta versión el único valor es `KILOGRAMO` (README, D-03).
  - `descripcion`: opcional, hasta 500 caracteres.
- **RQ-CUL-02**: La combinación `nombre` + `variedad` es única sin distinguir mayúsculas ni minúsculas. Un duplicado responde `409 CULTIVO_DUPLICADO`.
- **RQ-CUL-03**: El sistema debe permitir modificar `nombre`, `variedad` y `descripcion` con las mismas reglas. `unidadMedida` no cambia en esta versión, porque `KILOGRAMO` es su único valor.
- **RQ-CUL-04**: El sistema debe listar cultivos paginados, ordenados por nombre y variedad, con filtro opcional por texto en el nombre.
- **RQ-CUL-05**: El sistema debe devolver el detalle de un cultivo por ID, o `404 CULTIVO_NO_ENCONTRADO`.
- **RQ-CUL-06**: Toda creación y modificación genera un registro de auditoría.
- **RQ-CUL-07**: Esta versión no incluye eliminación de cultivos.

### Entidades clave

- **Cultivo** (agregado): `id` (UUID), `nombre`, `variedad`, `unidadMedida`, `descripcion`, `fechaCreacion`, `fechaActualizacion`.
- **UnidadProduccion**: `KILOGRAMO` (glosario de la constitución v2.2.0). Agregar otra unidad exige revisar D-03 y los indicadores (`spec-indicadores.md`), y definir si se puede cambiar en cultivos con producción registrada.

## Permisos

| Operación | Roles |
|---|---|
| Registrar y modificar | `administrador` |
| Listar y ver detalle | `administrador`, `gerencia`, cuentas de servicio autorizadas |

## Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Formato incorrecto o longitud excedida |
| 404 | `CULTIVO_NO_ENCONTRADO` | El ID no existe |
| 409 | `CULTIVO_DUPLICADO` | Ya existe el mismo nombre + variedad |
| 409 | `CONFLICTO_CONCURRENCIA` | El cultivo cambió desde que se leyó |

## Criterios de éxito

- **CE-CUL-01**: No pueden existir dos cultivos con el mismo nombre + variedad, ni siquiera ante solicitudes concurrentes.
- **CE-CUL-02**: Listado y detalle responden en menos de 3 s (RNF-05).
- **CE-CUL-03**: Toda creación y modificación tiene su registro de auditoría.

## Supuestos

- El cultivo es un catálogo simple: no guarda ciclo de días, densidad de siembra ni rendimiento esperado.
- El cultivo guarda su unidad de medida de producción (RF-02), pero por decisión D-03 todos los cultivos usan `KILOGRAMO`. Así el rendimiento siempre se expresa en kg/ha y es comparable entre cultivos.

## Aclaraciones

- **AC-01** — Resuelta (2026-11-01): RF-02 exige la unidad de medida de producción; se agrega `unidadMedida`, limitada a `KILOGRAMO` por D-03.

## Fuera de alcance

- Eliminación de cultivos.
- Datos agronómicos (ciclo, densidad, rendimiento esperado).


---

# 2. Plan

Reutiliza la base del servicio (Fase 0 de `spec-parcelas.md`): seguridad, errores, correlación, auditoría, paginación y tests de integración. Criterio: lo mínimo que cumple la spec.

## 2.1 Endpoints

Prefijo: `/api/gestion/v1`.

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /cultivos` | `administrador` | `201` + `Location` + cultivo | 400, 401, 403, 409 `CULTIVO_DUPLICADO` |
| `GET /cultivos?nombre=&pagina=&tamanio=` | `administrador`, `gerencia`, `lectura_gestion` | `200` + página | 400, 401, 403 |
| `GET /cultivos/{id}` | Igual que el listado | `200` + cultivo | 401, 403, 404 `CULTIVO_NO_ENCONTRADO` |
| `PUT /cultivos/{id}` | `administrador` | `200` + cultivo | 400, 401, 403, 404, 409 `CULTIVO_DUPLICADO` o `CONFLICTO_CONCURRENCIA` |

**Solicitud de creación** (la de modificación agrega `version`):

```json
{
  "nombre": "Soya",
  "variedad": "Munasqa",
  "unidadMedida": "KILOGRAMO",
  "descripcion": "Ciclo de verano"
}
```

**Respuesta:** los mismos campos más `id`, `version`, `fechaCreacion` y `fechaActualizacion`.

**Validaciones del DTO** (`400 DATOS_INVALIDOS`): `nombre` `@NotBlank @Size(max = 100)`; `variedad` `@Size(max = 100)`; `unidadMedida` `@NotNull` y valor de `UnidadProduccion` (cualquier otro texto falla al convertir el enum); `descripcion` `@Size(max = 500)`; `version` `@NotNull` en `PUT`.

## 2.2 Modelo de datos

**`V3__crear_cultivo.sql`**

```sql
CREATE TABLE cultivo (
    id                   UUID PRIMARY KEY,
    nombre               VARCHAR(100) NOT NULL,
    variedad             VARCHAR(100),
    unidad_medida        VARCHAR(20)  NOT NULL CHECK (unidad_medida IN ('KILOGRAMO')),
    descripcion          VARCHAR(500),
    version              BIGINT       NOT NULL,
    fecha_creacion       TIMESTAMPTZ  NOT NULL,
    fecha_actualizacion  TIMESTAMPTZ  NOT NULL
);
CREATE UNIQUE INDEX ux_cultivo_nombre_variedad
    ON cultivo (lower(nombre), lower(coalesce(variedad, '')));
```

## 2.3 Diseño por capas

| Capa | Clase | Responsabilidad |
|---|---|---|
| `domain/crop` | `Cultivo` | Agregado. Recorta textos; una variedad vacía se guarda como `null` |
| `domain/crop` | `UnidadProduccion` | Enum con `KILOGRAMO` |
| `domain/crop` | `RepositorioCultivo` | Puerto: `guardar`, `buscarPorId`, `listar` |
| `application/crop` | `CrearCultivoCasoUso`, `ActualizarCultivoCasoUso`, `ConsultarCultivoCasoUso`, `ListarCultivosCasoUso` | Igual que en parcelas; auditan `CREAR` y `MODIFICAR` |
| `infrastructure/persistence` | `CultivoEntidad`, `CultivoSpringData`, `MapeadorCultivo`, `RepositorioCultivoJpa` | Traduce la violación de `ux_cultivo_nombre_variedad` a `CULTIVO_DUPLICADO` |
| `interfaces/rest` | `CultivoControlador` + DTO | Igual que en parcelas |

**Unidad de medida (RQ-CUL-03):** mientras `UnidadProduccion` tenga un solo valor, la unidad nunca puede cambiar: cualquier otro valor falla al convertir el enum con `400 DATOS_INVALIDOS`.

## 2.4 Tests

| Tipo | Clase | Qué verifica |
|---|---|---|
| Unitario | `CultivoTest` | Recorte de textos y variedad vacía como `null` |
| Integración | `CultivoControladorIT` | Escenarios de las historias 1 a 3, incluida la unidad inválida y la auditoría |
| Integración | `CultivoConcurrenciaIT` | Dos creaciones simultáneas con el mismo nombre y variedad → una `409` |

# 3. Tareas

- [x] **T01** — Crear `Cultivo` y `UnidadProduccion`, con `CultivoTest`.
- [x] **T02** — Crear `V3__crear_cultivo.sql` y la persistencia, con la traducción del índice único a `CULTIVO_DUPLICADO`.
- [x] **T03** — Implementar `POST /cultivos`. *Hecho cuando:* pasan los escenarios de la historia 1.
- [x] **T04** — Implementar los dos `GET`. *Hecho cuando:* pasan los escenarios de la historia 2.
- [x] **T05** — Implementar `PUT /cultivos/{id}`. *Hecho cuando:* pasan los escenarios de la historia 3.
- [x] **T06** — Escribir `CultivoConcurrenciaIT` y documentar los errores en OpenAPI.
- [x] **T07** — Verificación final: `mvn verify` en verde y criterios CE-CUL-01 a CE-CUL-03 cubiertos.
