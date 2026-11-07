# Consultas de solo lectura para integración — `servicio-gestion`

| Campo | Valor |
|---|---|
| Servicio | `servicio-gestion` |
| Archivo | `specs/spec-consultas-integracion.md` |
| Estado | Spec aprobada (2026-11-01) · Implementada (2026-11-02) |
| Fecha | 2026-11-01 |
| Constitución | v2.7.0 (sección 5) |
| Trazabilidad | Soporte de CU-10, CU-12, CU-14, CU-17 y CU-18 · RF-18, RF-23, RF-27 · RN-06, RN-14 · RNF-05, RNF-08, RNF-09 |
| Depende de | `spec-campanias.md`, `spec-produccion.md` y `spec-indicadores.md` |


Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Contexto

Tres clientes técnicos leen datos de este servicio, siempre a través del API Gateway y con su cuenta de servicio de Keycloak:

| Cliente | Para qué | Consulta |
|---|---|---|
| `servicio-operaciones` | Validar que una labor se registra en una campaña existente, no finalizada y de esa parcela (RN-06) | Estado de campaña |
| `servicio-ia` (MCP y entrenamiento) | Entrenar el modelo de rendimiento y responder consultas de agentes (RF-18) | Históricos de campañas |
| Servidor GraphQL | Mostrar campañas e indicadores en los frontends | Campañas (`spec-campanias.md`) e indicadores (`spec-indicadores.md`) |

Este servicio no llama a ninguno de ellos.

## Escenarios de usuario y pruebas

### Historia 1 — Consultar el estado de una campaña para validar una labor (Prioridad: P1)

Como `servicio-operaciones`, quiero consultar rápidamente si una campaña existe, en qué estado está y a qué parcela pertenece, para aceptar o rechazar labores (RN-06).

**Por qué esta prioridad:** es la única llamada síncrona que recibe el servicio y bloquea el registro de labores si falla.

**Prueba independiente:** con la cuenta de servicio de operaciones, se consulta una campaña en cada estado y una inexistente.

**Escenarios de aceptación:**

1. **Dado** una campaña `EN_CURSO`, **cuando** `servicio-operaciones` la consulta, **entonces** recibe `id`, `idParcela`, `idCultivo`, `estado`, `fechaInicio` y `fechaFin`.
2. **Dado** una campaña `FINALIZADA`, **cuando** la consulta, **entonces** recibe `estado = FINALIZADA` (la decisión de rechazar la labor la toma `servicio-operaciones`).
3. **Dado** un ID inexistente, **entonces** recibe `404 CAMPANIA_NO_ENCONTRADA`.
4. **Dado** una cuenta de servicio sin este permiso, **entonces** recibe `403 SIN_PERMISO`.

---

### Historia 2 — Obtener datos históricos de campañas (Prioridad: P1)

Como `servicio-ia`, quiero obtener las campañas finalizadas con sus características, producción, costos e indicadores, para entrenar el modelo de rendimiento y responder consultas de los agentes (RF-18).

**Por qué esta prioridad:** sin históricos no hay modelo de rendimiento.

**Prueba independiente:** con campañas finalizadas y en curso, se piden los históricos y se verifica que solo vienen las finalizadas, con todos sus campos.

**Escenarios de aceptación:**

1. **Dado** campañas en varios estados, **cuando** `servicio-ia` pide los históricos, **entonces** recibe solo las `FINALIZADA`, paginadas y ordenadas por `fechaFinalizacion` descendente.
2. **Dado** el filtro `idCultivo` y un rango de `fechaFinalizacion`, **entonces** recibe solo las que coinciden.
3. **Dado** una campaña histórica, **entonces** cada registro incluye: `idCampania`, `idParcela`, `nombreParcela`, `superficieHectareas`, `idCultivo`, `nombreCultivo`, `variedad`, `fechaInicio`, `fechaFin`, `fechaInicioEjecucion`, `fechaFinalizacion`, `duracionDias`, `produccion`, `fechaCosecha`, `costoTotal` (solo costos vigentes), costo por categoría (`INSUMO`, `MANO_DE_OBRA`, `MAQUINARIA`, `OTRO`, con `0,00` si no hay), `rendimientoPorHectarea`, `costoPorHectarea` y `motivosNoDisponible`.
4. **Dado** una campaña finalizada sin costos vigentes, **entonces** `rendimientoPorHectarea` y `costoPorHectarea` son `null` y `motivosNoDisponible` contiene `SIN_COSTOS` (RN-03).
5. **Dado** una cuenta de servicio con permiso de lectura, **cuando** intenta modificar datos, **entonces** recibe `403 SIN_PERMISO` (RN-14 desde el lado de este servicio).

---

### Historia 3 — Consultar campañas e indicadores desde GraphQL (Prioridad: P2)

Como servidor GraphQL, quiero leer campañas, parcelas, cultivos e indicadores con mi cuenta de servicio, para componer las vistas de los frontends.

**Prueba independiente:** con la cuenta de servicio de GraphQL se usan las consultas de las `spec-parcelas.md`, `spec-cultivos.md`, `spec-campanias.md` y `spec-indicadores.md`.

**Escenarios de aceptación:**

1. **Dado** la cuenta de servicio de GraphQL, **cuando** consulta listados y detalles de las `spec-parcelas.md`, `spec-cultivos.md`, `spec-campanias.md` e indicadores de la `spec-indicadores.md`, **entonces** recibe los mismos datos que un usuario `gerencia`.
2. **Dado** la misma cuenta, **cuando** intenta crear o modificar algo, **entonces** recibe `403 SIN_PERMISO`.

---

### Casos borde

- `servicio-ia` pide una página fuera de rango: lista vacía con el total real, no error.
- Rango de fechas invertido (desde > hasta): `400 DATOS_INVALIDOS`.
- Tamaño de página mayor al máximo: `400 DATOS_INVALIDOS`.
- Una campaña se finaliza mientras `servicio-ia` pagina: puede aparecer en la siguiente lectura; el orden por `fechaFinalizacion` y un ID de desempate evitan duplicados dentro de una misma lectura estable.

## Requisitos

### Requisitos funcionales

- **RQ-INT-01**: El sistema debe exponer una consulta resumida de campaña por ID que devuelva `id`, `idParcela`, `idCultivo`, `estado`, `fechaInicio` y `fechaFin`, sin costos ni producción, optimizada para responder rápido.
- **RQ-INT-02**: El sistema debe exponer una consulta de históricos que devuelva solo campañas `FINALIZADA`, con los campos de la Historia 2, escenario 3.
- **RQ-INT-03**: La consulta de históricos admite filtros opcionales por `idCultivo`, `idParcela` y rango de `fechaFinalizacion`; paginada, con tamaño máximo de página 500 (ver D-05 del README).
- **RQ-INT-04**: Los indicadores de los históricos se calculan con las mismas reglas de la `spec-indicadores.md` (RN-03).
- **RQ-INT-05**: Todas las consultas de esta spec son de solo lectura y no generan auditoría (la auditoría es para creaciones y modificaciones).
- **RQ-INT-06**: Las cuentas de servicio solo tienen permisos de lectura, mediante dos roles de realm:

  | Rol | Cuentas de servicio | Permite |
  |---|---|---|
  | `estado_campania` | `servicio-operaciones`, GraphQL | Consulta de estado de campaña |
  | `lectura_gestion` | `servicio-ia`, GraphQL | Históricos y consultas de `spec-parcelas.md`, `spec-cultivos.md`, `spec-campanias.md` y `spec-indicadores.md` |

  n8n no tiene permisos en este servicio.

- **RQ-INT-07**: Toda respuesta propaga el `X-Correlation-Id` recibido.

### Entidades clave

No introduce entidades nuevas. Usa proyecciones de lectura de `Campania`, `Parcela`, `Cultivo`, `ProduccionCampania`, `CostoCampania` e `IndicadoresCampania`.

## Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Filtros o paginación inválidos |
| 401 | `NO_AUTENTICADO` | Sin token o token inválido |
| 403 | `SIN_PERMISO` | La cuenta no tiene permiso para esa consulta |
| 404 | `CAMPANIA_NO_ENCONTRADA` | La campaña no existe |

## Criterios de éxito

- **CE-INT-01**: La consulta de estado de campaña responde en menos de 3 s (RNF-05), con objetivo p95 menor a 300 ms para no agotar el tiempo límite de `servicio-operaciones`.
- **CE-INT-02**: Una página de 500 históricos responde en menos de 3 s con al menos 5.000 campañas finalizadas.
- **CE-INT-03**: Ninguna cuenta de servicio puede ejecutar operaciones de escritura (tests de integración por cuenta).

## Supuestos

- `servicio-ia` no guarda copias permanentes de estos datos (su constitución, sección 4); los pide en cada uso.
- Todas las campañas `FINALIZADA` tienen producción (`spec-campanias.md`, AC-01, resuelta), pero pueden no tener costos.

## Aclaraciones

- **AC-01** — Resuelta (2026-11-01): sin consulta de indicadores por lote (`spec-indicadores.md`, AC-01).
- **AC-02** — Resuelta (2026-11-01): n8n no tiene permisos de lectura en este servicio mientras no aparezca una necesidad en una spec.

## Fuera de alcance

- Escrituras desde cuentas de servicio (solo la Saga escribe, por mensajería, `spec-costo-saga.md`).
- Exportaciones masivas o descargas de archivos.


---

# 2. Plan

Reutiliza la base del servicio (Fase 0 de `spec-parcelas.md`), el agregado `Campania` e `IndicadoresCampania`. No crea tablas; agrega el índice de históricos. Criterio: lo mínimo que cumple la spec.

## 2.1 Endpoints

Prefijo: `/api/gestion/v1`.

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `GET /campanias/{id}/estado` | `estado_campania` | `200` + estado resumido | 401, 403, 404 `CAMPANIA_NO_ENCONTRADA` |
| `GET /campanias/historicos?idCultivo=&idParcela=&fechaFinalizacionDesde=&fechaFinalizacionHasta=&pagina=&tamanio=` | `lectura_gestion` | `200` + página (máximo 500 por página) | 400, 401, 403 |

GraphQL usa además las consultas de `spec-parcelas.md`, `spec-cultivos.md`, `spec-campanias.md` y `spec-indicadores.md` con su rol `lectura_gestion`; no requieren nada nuevo aquí.

**Estado resumido:**

```json
{
  "id": "uuid",
  "idParcela": "uuid",
  "idCultivo": "uuid",
  "estado": "EN_CURSO",
  "fechaInicio": "2026-11-15",
  "fechaFin": "2027-03-30"
}
```

**Registro de históricos:**

```json
{
  "idCampania": "uuid",
  "idParcela": "uuid",
  "nombreParcela": "Lote Norte",
  "superficieHectareas": "25.5000",
  "idCultivo": "uuid",
  "nombreCultivo": "Soya",
  "variedad": "Munasqa",
  "fechaInicio": "2026-11-15",
  "fechaFin": "2027-03-30",
  "fechaInicioEjecucion": "2026-11-16T12:00:00Z",
  "fechaFinalizacion": "2027-03-28T18:00:00Z",
  "duracionDias": 133,
  "produccion": "76500.00",
  "fechaCosecha": "2027-03-20",
  "costoTotal": "38250.00",
  "costosPorCategoria": { "INSUMO": "20000.00", "MANO_DE_OBRA": "12000.00", "MAQUINARIA": "6250.00", "OTRO": "0.00" },
  "rendimientoPorHectarea": "3000.00",
  "costoPorHectarea": "1500.00",
  "motivosNoDisponible": []
}
```

`duracionDias` se calcula entre `fechaInicio` y la fecha de finalización en UTC. `motivosNoDisponible` sigue las reglas de `spec-indicadores.md`. Los filtros de `fechaFinalizacion` son fechas sin hora y cubren días completos en UTC. El orden es `fechaFinalizacion` descendente y, como desempate, `id`.

**Validación de parámetros** (`400 DATOS_INVALIDOS`): `tamanio` hasta 500 en históricos; `fechaFinalizacionDesde` posterior a `fechaFinalizacionHasta`.

## 2.2 Diseño por capas

| Capa | Clase | Responsabilidad |
|---|---|---|
| `application/campaign` | `ConsultarEstadoCampaniaCasoUso`, `ConsultaEstadoCampania` | Lee solo los campos del estado resumido mediante un puerto de lectura (proyección, sin cargar costos) |
| `application/campaign` | `ListarHistoricosCasoUso` | Obtiene las filas y calcula los indicadores con `IndicadoresCampania` (RN-03) |
| `application/campaign` | `ConsultaHistoricos` | Puerto de lectura que devuelve filas planas (no es un repositorio de agregado) |
| `infrastructure/persistence` | `ConsultaEstadoCampaniaJdbc`, `ConsultaHistoricosJdbc` | Usan JDBC, sin JPA. Históricos: una consulta SQL que elige primero la página de campañas (índice `ix_campania_historicos`, `V8__crear_indice_historicos.sql`), la une con `parcela`, `cultivo` y `produccion_campania`, y suma solo para esas campañas los costos no anulados por categoría (`SUM ... FILTER (WHERE categoria = ...)`) |
| `interfaces/rest` | `IntegracionControlador` + DTO | Traduce HTTP |

Las lecturas no generan auditoría (RQ-INT-05).

## 2.3 Tests

| Tipo | Clase | Qué verifica |
|---|---|---|
| Integración | `EstadoCampaniaIT` | Historia 1: cada estado, 404, rol sin permiso → 403 |
| Integración | `HistoricosIT` | Historia 2: solo finalizadas, filtros, campos completos, costos anulados excluidos, finalizada sin costos con motivo `SIN_COSTOS`, página fuera de rango vacía con total real, rango de fechas invertido → 400 |
| Integración | `PermisosIntegracionIT` | Historia 3 y RQ-INT-06: con `lectura_gestion` y `estado_campania` no se puede crear ni modificar nada (CE-INT-03) |
| Integración | `IntegracionRendimientoIT` | Estado en menos de 3 s; página de 500 históricos con 5.000 campañas finalizadas en menos de 3 s (CE-INT-01 y CE-INT-02) |

# 3. Tareas

- [x] **T01** — Implementar `GET /campanias/{id}/estado`. *Hecho cuando:* pasa `EstadoCampaniaIT`.
- [x] **T02** — Implementar `ConsultaHistoricos` con la consulta SQL agregada.
- [x] **T03** — Implementar `GET /campanias/historicos`. *Hecho cuando:* pasa `HistoricosIT`.
- [x] **T04** — Escribir `PermisosIntegracionIT` e `IntegracionRendimientoIT`; documentar los errores en OpenAPI.
- [x] **T05** — Verificación final: `mvn verify` en verde y criterios CE-INT-01 a CE-INT-03 cubiertos.
