# Estado del inventario — `servicio-inventario`

| Campo | Valor |
|---|---|
| Servicio | `servicio-inventario` |
| Archivo | `specs/spec-estado-inventario.md` |
| Estado | Spec en borrador (2026-11-02) · Plan y tareas en borrador |
| Constitución | v2.8.0 (sección 5) |
| Trazabilidad | CU-24 (prioridad media) · RF-33, RF-27 · RN-05, RN-14, RN-15, RN-16 · RNF-05 |
| Depende de | `spec-insumos.md`, `spec-movimientos.md` |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Contexto

Tres clientes leen el estado del inventario (constitución §5):

| Cliente | Para qué |
|---|---|
| Angular (administrador y gerencia, a través del Gateway) | Tablero del inventario con los insumos en stock bajo |
| Servidor GraphQL | Componer las vistas de los frontends |
| `servicio-ia` (MCP y agentes) | Responder consultas como "¿qué insumos están por agotarse?" |

Es una consulta de solo lectura: no cambia nada ni genera auditoría.

## Escenarios de usuario y pruebas

### Historia 1 — Ver qué insumos están en stock bajo (Prioridad: P1)

Como gerente, quiero ver el estado de todos los insumos frente a su nivel mínimo, con los que están en stock bajo primero, para decidir reposiciones (RF-33).

**Por qué esta prioridad:** es el requisito RF-33 y la vista que complementa la alerta por correo.

**Prueba independiente:** con insumos por encima, en y por debajo del nivel mínimo, se consulta el estado.

**Escenarios de aceptación:**

1. **Dado** "Urea" (stock 40, mínimo 50), "Glifosato" (stock 20, mínimo 20) y "Semilla de maíz" (stock 300, mínimo 100), **cuando** se consulta el estado, **entonces** "Glifosato" y "Urea" vienen primero con `stockBajo = true` (ordenados por nombre), y después "Semilla de maíz" con `stockBajo = false`.
2. **Dado** lo mismo, **entonces** el resumen indica `totalInsumos = 3` y `totalStockBajo = 2`.
3. **Dado** el filtro `soloStockBajo=true`, **entonces** solo vienen "Glifosato" y "Urea", y el resumen sigue contando todo el inventario.
4. **Dado** el filtro `categoria=FERTILIZANTE`, **entonces** solo vienen los fertilizantes, y el resumen cuenta solo esa categoría.
5. **Dado** un insumo con stock 0 y mínimo 0, **entonces** aparece con `stockBajo = true` (regla `stock <= nivelMinimo`).
6. **Dado** un insumo que ya generó una alerta, **entonces** su `fechaUltimaAlerta` aparece en la respuesta.

---

### Historia 2 — Leer el estado desde integraciones (Prioridad: P2)

Como `servicio-ia`, GraphQL o n8n, quiero leer el estado del inventario con mi cuenta de servicio, sin poder modificar nada (RN-14).

**Prueba independiente:** con un token con `lectura_inventario` se consulta el estado y se intenta escribir.

**Escenarios de aceptación:**

1. **Dado** una cuenta con `lectura_inventario`, **cuando** consulta el estado, **entonces** recibe la misma respuesta que `gerencia`.
2. **Dado** un usuario que solo tiene `tecnico_campo`, **cuando** consulta el estado, **entonces** recibe `403 SIN_PERMISO`.

---

### Casos borde

- Página fuera de rango: lista vacía con el resumen y el total reales, no error.
- Un movimiento ocurre mientras se pagina: el orden por (`stockBajo`, `nombre`, `id`) es estable dentro de una misma lectura; el siguiente pedido puede mover el insumo de grupo.
- Cambiar el nivel mínimo de un insumo con `PUT` cambia su `stockBajo` en la siguiente consulta, aunque no genere alerta (la alerta solo se evalúa tras un movimiento; `spec-stock-bajo.md`).

## Requisitos

### Requisitos funcionales

- **RQ-EST-01**: El sistema debe exponer el estado del inventario: por insumo, `idInsumo`, `nombre`, `categoria`, `unidad`, `stock`, `nivelMinimo`, `stockBajo` y `fechaUltimaAlerta`.
- **RQ-EST-02**: `stockBajo` es `true` si `stock <= nivelMinimo` (RN-05, la misma regla del evento).
- **RQ-EST-03**: Orden: primero los insumos con `stockBajo = true`, después el resto; dentro de cada grupo por nombre y, para desempatar, por `id`.
- **RQ-EST-04**: Filtros opcionales `categoria` y `soloStockBajo`; paginado (README D-04).
- **RQ-EST-05**: La respuesta incluye un `resumen` con `totalInsumos` y `totalStockBajo`, calculado sobre la categoría filtrada (o todo el inventario) e independiente de `soloStockBajo` y de la página.
- **RQ-EST-06**: Es de solo lectura y no genera auditoría.
- **RQ-EST-07**: No incluye datos económicos (`costoUnitario`); quien los necesite usa `GET /insumos`.

### Entidades clave

No introduce entidades nuevas: es una proyección de lectura de `Insumo`.

## Permisos

| Operación | Roles |
|---|---|
| Consultar el estado del inventario | `administrador`, `gerencia`, `lectura_inventario` |

## Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Categoría inválida, `soloStockBajo` no booleano, paginación fuera de rango |

## Criterios de éxito

- **CE-EST-01**: Con 1.000 insumos, la consulta responde en menos de 3 s (RNF-05).
- **CE-EST-02**: `stockBajo` coincide con la regla del evento en todos los casos límite (stock igual, mayor y menor al mínimo; mínimo 0).
- **CE-EST-03**: El resumen coincide con un conteo independiente en el test.

## Supuestos

- La cantidad de insumos es pequeña (cientos), por lo que el cálculo se hace en cada consulta, sin vistas materializadas.

## Fuera de alcance

- Valorización del inventario (stock × costo).
- Proyección de agotamiento o consumo promedio (lo puede hacer `servicio-ia` con los movimientos, si se pide en una spec futura).

---

# 2. Plan

Reutiliza `insumos` y el repositorio de `spec-insumos.md`. Una sola agregación de MongoDB.

## 2.1 Endpoint

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `GET /estado-inventario?categoria=&soloStockBajo=&pagina=&tamanio=` | `administrador`, `gerencia`, `lectura_inventario` | `200` | 400, 401, 403 |

**Respuesta:**

```json
{
  "resumen": { "totalInsumos": 3, "totalStockBajo": 2 },
  "items": [
    {
      "idInsumo": "71aa…",
      "nombre": "Glifosato",
      "categoria": "FITOSANITARIO",
      "unidad": "LITRO",
      "stock": "20.000",
      "nivelMinimo": "20.000",
      "stockBajo": true,
      "fechaUltimaAlerta": "2026-11-02T10:15:00Z"
    }
  ],
  "pagina": 0,
  "tamanio": 20,
  "total": 3
}
```

## 2.2 Consulta

`RepositorioInsumoMongo.consultarEstado(filtros, pagina, tamanio)` con una agregación:

```text
$match       { categoria? }
$addFields   { stock_bajo: { $lte: ["$stock", "$nivel_minimo"] } }
$facet
  resumen:   [ $group { _id: null, total: $sum 1, total_bajo: $sum { $cond: ["$stock_bajo", 1, 0] } } ]
  pagina:    [ $match { stock_bajo: true }?  (solo si soloStockBajo)
               $sort { stock_bajo: -1, nombre_normalizado: 1, _id: 1 }
               $skip / $limit ]
  total:     [ $match { stock_bajo: true }?, $count ]
```

- `$lte` compara `Decimal128` con exactitud.
- El índice `{ categoria: 1, nombre_normalizado: 1 }` de `spec-insumos.md` cubre el filtro por categoría; con cientos de insumos no hace falta otro índice.

## 2.3 Diseño por capas

| Capa | Archivo | Responsabilidad |
|---|---|---|
| `domain/supply` | `politica-stock-bajo.ts` | `estaEnStockBajo(stock, nivelMinimo)`: la regla de RQ-EST-02, compartida con `spec-stock-bajo.md` |
| `application/use-cases` | `consultar-estado-inventario.caso-uso.ts` | Valida filtros y delega en el repositorio |
| `application/ports` | `repositorio-insumo.puerto.ts` (se amplía) | `consultarEstado` |
| `adapters/inbound/http` | `estado-inventario.controlador.ts`, `dto/` | HTTP ↔ caso de uso |

La agregación replica en MongoDB la regla de `politica-stock-bajo.ts`; el test CE-EST-02 verifica que ambas coinciden.

## 2.4 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `politica-stock-bajo.spec.ts` | Stock menor, igual y mayor al mínimo; mínimo 0 |
| Integración | `estado-inventario.controlador.int-spec.ts` | Historias 1 y 2, casos borde; resumen contra un conteo del test (CE-EST-03); misma respuesta que la política del dominio para cada insumo (CE-EST-02) |
| Integración | `estado-inventario-rendimiento.int-spec.ts` | CE-EST-01 |

---

# 3. Tareas

- [x] **T01** — Crear `politica-stock-bajo.ts` (solo `estaEnStockBajo`) con su test unitario. Adelantada en `spec-insumos.md`, porque la vista completa del insumo incluye `stockBajo`; sus tests están en `insumo.entidad.spec.ts`.
- [ ] **T02** — Implementar `consultarEstado` en el repositorio, `ConsultarEstadoInventarioCasoUso` y `GET /estado-inventario`. *Hecho cuando:* pasan las Historias 1 y 2.
- [ ] **T03** — Escribir los casos borde y CE-EST-02, CE-EST-03.
- [ ] **T04** [P] — Escribir `estado-inventario-rendimiento.int-spec.ts` (CE-EST-01).
- [ ] **T05** — Documentar el endpoint en OpenAPI y verificación final (`npm test` en verde, cobertura ≥ 80 %).
