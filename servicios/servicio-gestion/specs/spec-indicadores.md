# Indicadores de campaña — `servicio-gestion`

| Campo | Valor |
|---|---|
| Servicio | `servicio-gestion` |
| Archivo | `specs/spec-indicadores.md` |
| Estado | Spec aprobada (2026-11-01) · Implementada (2026-11-02) |
| Fecha | 2026-11-01 |
| Constitución | v2.7.0 |
| Trazabilidad | CU-05 (prioridad media) · RF-06 · RN-03, RN-15 · RNF-05 |
| Depende de | `spec-campanias.md`, `spec-costos-manuales.md`, `spec-produccion.md` |


Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Escenarios de usuario y pruebas

### Historia 1 — Ver el rendimiento y el costo por hectárea (Prioridad: P1)

Como gerente, quiero ver el rendimiento por hectárea y el costo por hectárea de una campaña, para evaluar su desempeño.

**Por qué esta prioridad:** es el resultado de negocio que justifica registrar costos y producción.

**Prueba independiente:** con una campaña que tiene producción y costos, se consultan los indicadores y se verifican los valores calculados.

**Escenarios de aceptación:**

1. **Dado** una campaña de 25,5 ha con producción de 76.500 kg y costos por Bs 38.250,00, **cuando** se consultan sus indicadores, **entonces** se devuelve rendimiento = 3.000,00 kg/ha, costo por hectárea = Bs 1.500,00/ha y costo total = Bs 38.250,00.
2. **Dado** una campaña con costos pero sin producción, **cuando** se consultan sus indicadores, **entonces** rendimiento y costo por hectárea son `null` con el motivo `SIN_PRODUCCION`; nunca `0` (RN-03).
3. **Dado** una campaña con producción pero sin costos, **entonces** ambos indicadores son `null` con el motivo `SIN_COSTOS`.
4. **Dado** una campaña sin producción ni costos, **entonces** ambos indicadores son `null` con los motivos `SIN_PRODUCCION` y `SIN_COSTOS`.
5. **Dado** una campaña con producción 0 (pérdida total) y costos, **entonces** el rendimiento es `0,00` y el costo por hectárea se calcula normalmente.
6. **Dado** un usuario con rol `tecnico_campo` (sin otro rol), **cuando** consulta indicadores, **entonces** se responde `403 SIN_PERMISO`.

---

### Historia 2 — Distinguir indicadores provisionales y definitivos (Prioridad: P2)

Como gerente, quiero saber si los indicadores de una campaña pueden cambiar todavía, para no tomar decisiones con números provisionales.

**Escenarios de aceptación:**

1. **Dado** una campaña `EN_CURSO` con producción y costos, **cuando** se consultan sus indicadores, **entonces** se devuelven calculados con `definitivo = false`.
2. **Dado** una campaña `FINALIZADA`, **entonces** se devuelven con `definitivo = true`.

---

### Casos borde

- Un costo de la Saga llega entre dos consultas: la segunda consulta ya lo refleja (los indicadores se calculan en cada consulta, sin caché).
- Divisiones con decimales periódicos (por ejemplo, 100.000 kg en 30 ha): se calcula con precisión completa y se redondea al final a 2 decimales, mitad hacia arriba.
- Campaña inexistente: `404 CAMPANIA_NO_ENCONTRADA`.

## Requisitos

### Requisitos funcionales

- **RQ-IND-01**: El sistema debe devolver, para una campaña:
  - `costoTotal`: suma de sus costos vigentes (manuales y de la Saga, sin los anulados por compensación). Es `0,00` si no hay costos: es una suma real, no un indicador.
  - `rendimientoPorHectarea` = producción ÷ `superficieHectareas` de la campaña, en kg/ha (README, D-03).
  - `costoPorHectarea` = `costoTotal` ÷ `superficieHectareas`, en Bs/ha (README, D-01).
- **RQ-IND-02**: `rendimientoPorHectarea` y `costoPorHectarea` solo se calculan si la campaña tiene producción registrada **y** al menos un costo vigente (RN-03). Si falta alguno, ambos son `null` y la respuesta incluye los motivos: `SIN_PRODUCCION`, `SIN_COSTOS` o ambos. Nunca se devuelve `0` por falta de datos.
- **RQ-IND-03**: Los cálculos usan aritmética decimal exacta y se redondean al final a 2 decimales, mitad hacia arriba.
- **RQ-IND-04**: La respuesta incluye `estadoCampania`, `superficieHectareas`, la producción usada (o `null`) y `definitivo` (`true` solo si la campaña está `FINALIZADA`).
- **RQ-IND-05**: Los indicadores se calculan en cada consulta a partir de los datos vigentes; no se guardan.
- **RQ-IND-06**: El cálculo vive en el dominio (`IndicadoresCampania`), no en el controlador.

Ejemplo orientativo de respuesta (el contrato definitivo va en OpenAPI):

```json
{
  "idCampania": "uuid",
  "estadoCampania": "EN_CURSO",
  "definitivo": false,
  "superficieHectareas": "25.5000",
  "produccion": null,
  "costoTotal": "38250.00",
  "rendimientoPorHectarea": null,
  "costoPorHectarea": null,
  "motivosNoDisponible": ["SIN_PRODUCCION"]
}
```

### Entidades clave

- **IndicadoresCampania** (objeto de valor del dominio): `costoTotal`, `rendimientoPorHectarea`, `costoPorHectarea`, `motivosNoDisponible`, `definitivo`.
- **MotivoIndicadorNoDisponible**: `SIN_PRODUCCION` / `SIN_COSTOS` (glosario de la constitución v2.1.0).

## Permisos

| Operación | Roles |
|---|---|
| Consultar indicadores | `administrador`, `gerencia`, cuentas de servicio autorizadas (GraphQL, `servicio-ia`) |

## Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 404 | `CAMPANIA_NO_ENCONTRADA` | La campaña no existe |

La falta de datos para calcular **no** es un error: responde `200` con indicadores `null` y sus motivos.

## Criterios de éxito

- **CE-IND-01**: En el 100 % de los casos sin producción o sin costos, los indicadores son `null` con su motivo; nunca `0` (tests unitarios de cada combinación).
- **CE-IND-02**: Los valores coinciden al centavo con un cálculo de referencia en todos los tests.
- **CE-IND-03**: La consulta responde en menos de 3 s para una campaña con 1.000 costos (RNF-05).

## Supuestos

- La regla RN-03 se aplica literalmente: aunque el costo por hectárea podría calcularse sin producción, la constitución exige producción y costos para ambos indicadores.
- No se incluyen indicadores adicionales (margen, rentabilidad): ventas y rentabilidad están fuera del alcance del sistema.

## Aclaraciones

- **AC-01** — Resuelta (2026-11-01): no se incluye consulta de indicadores por lote; GraphQL usa la consulta por campaña. Se agregará con una spec nueva si aparece un problema de rendimiento medido.

## Fuera de alcance

- Indicadores agregados por parcela, cultivo o periodo.
- Comparación entre campañas (fuera del alcance del sistema).
- Predicciones (responsabilidad de `servicio-ia`).


---

# 2. Plan

Reutiliza la base del servicio (Fase 0 de `spec-parcelas.md`) y el agregado `Campania` con sus costos y producción. No crea tablas. Criterio: lo mínimo que cumple la spec.

## 2.1 Endpoint

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `GET /api/gestion/v1/campanias/{id}/indicadores` | `administrador`, `gerencia`, `lectura_gestion` | `200` + indicadores | 401, 403, 404 `CAMPANIA_NO_ENCONTRADA` |

**Respuesta** (igual al ejemplo de la spec):

```json
{
  "idCampania": "uuid",
  "estadoCampania": "FINALIZADA",
  "definitivo": true,
  "superficieHectareas": "25.5000",
  "produccion": "76500.00",
  "costoTotal": "38250.00",
  "rendimientoPorHectarea": "3000.00",
  "costoPorHectarea": "1500.00",
  "motivosNoDisponible": []
}
```

Si falta producción o costos: `rendimientoPorHectarea` y `costoPorHectarea` son `null` y `motivosNoDisponible` lista `SIN_PRODUCCION`, `SIN_COSTOS` o ambos.

## 2.2 Diseño por capas

| Capa | Clase | Responsabilidad |
|---|---|---|
| `domain/campaign` | `IndicadoresCampania` | Objeto de valor con un método `calcular(produccion, costoTotal, superficieHectareas, estado)`, para que también lo usen los históricos, que no cargan el agregado. Un `costoTotal` de 0 significa que no hay costos vigentes, porque todo monto es mayor a 0. Aplica RN-03, divide con precisión completa (`MathContext.DECIMAL128`) y redondea al final a 2 decimales `HALF_UP` |
| `domain/campaign` | `MotivoIndicadorNoDisponible` | Enum del glosario |
| `application/campaign` | `ConsultarIndicadoresCasoUso` | Carga la campaña (404) y calcula con sus datos vigentes |
| `interfaces/rest` | `IndicadoresControlador` + `IndicadoresRespuesta` | Traduce HTTP |

Los indicadores se calculan en cada consulta; no se guardan ni se cachean.

## 2.3 Tests

| Tipo | Clase | Qué verifica |
|---|---|---|
| Unitario | `IndicadoresCampaniaTest` | Las cuatro combinaciones de producción y costos; producción 0; división periódica (100.000 kg en 30 ha); costos anulados excluidos; `definitivo` según estado |
| Integración | `IndicadoresControladorIT` | Escenarios de las historias 1 y 2, el 403 de `tecnico_campo` y el 404 |
| Integración | `IndicadoresRendimientoIT` | 1.000 costos: respuesta en menos de 3 s (CE-IND-03) |

# 3. Tareas

- [x] **T01** — Crear `IndicadoresCampania` y `MotivoIndicadorNoDisponible`, con `IndicadoresCampaniaTest`.
- [x] **T02** — Implementar `ConsultarIndicadoresCasoUso` y el endpoint. *Hecho cuando:* pasa `IndicadoresControladorIT`.
- [x] **T03** — Escribir `IndicadoresRendimientoIT` y documentar los errores en OpenAPI.
- [x] **T04** — Verificación final: `mvn verify` en verde y criterios CE-IND-01 a CE-IND-03 cubiertos.
