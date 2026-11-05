# Modelos de IA — `servicio-ia`

Documentación de cada modelo: propósito, datos, variables, entrenamiento, métricas de la versión vigente, limitaciones y cómo reentrenarlo (constitución §5). Se actualiza en el mismo commit que publica una versión.

Todos los resultados son **orientativos** (RN-13): no sustituyen una evaluación técnica agrícola.

---

## Conjunto de referencia (rendimiento y patrones)

El sistema empieza sin campañas finalizadas, así que los dos modelos tabulares se entrenan con un conjunto de referencia construido a partir de un dataset público, más las campañas finalizadas de `servicio-gestion` cuando existan (`--incluir-historicos`).

| | |
|---|---|
| Fuente | USDA Economic Research Service, *Commodity Costs and Returns*, sección "Recent Cost and Returns": `corn.csv`, `soybeans.csv` y `sorghum.csv` (<https://www.ers.usda.gov/data-products/commodity-costs-and-returns>) |
| Cita | U.S. Department of Agriculture, Economic Research Service. Commodity Costs and Returns data. |
| Licencia | Publicación del gobierno federal de EE. UU. (dominio público en EE. UU.) |
| Cobertura | Una fila por cultivo, región productiva y año: maíz 1996-2025 (180 filas), soya 1997-2025 (203), sorgo 1995-2025 (102). Total: 485 |
| Archivos | `datos/referencia/campanias_referencia.csv` (conjunto), `datos/referencia/fuentes.json` (URL, SHA-256 y conversiones), `datos/referencia/ipc_eeuu.csv` (deflactor) |
| Regenerar | `python -m app.ml.datos.preparar_ers` (descarga) o `--origen <carpeta>` (CSV ya descargados) |

### Transformaciones

1. Se excluye la región `U.S. total` (es un agregado de las demás).
2. Los ítems de costo del ERS se agrupan en las categorías de `CostoCampania` de `servicio-gestion`:

   | Categoría | Ítems del ERS |
   |---|---|
   | `INSUMO` | Seed, Fertilizer, Chemicals |
   | `MAQUINARIA` | Custom services; Fuel, lube, and electricity; Repairs; Capital recovery of machinery and equipment |
   | `MANO_DE_OBRA` | Hired labor |
   | `OTRO` | Purchased irrigation water; Interest on operating capital (o *inputs*, en sorgo); Taxes and insurance; General farm overhead |
   | Excluidos | Opportunity cost of land; Opportunity cost of unpaid labor (costos implícitos que un productor no registra) |

3. Los montos se deflactan a dólares de 2025 con el IPC de EE. UU. (BLS CPI-U, `CUUR0000SA0`, promedio anual).
4. Unidades: USD/acre × 2,47105 × 6,96 → **BOB/ha**; bushels/acre × kg por bushel (soya 27,2155; maíz y sorgo 25,4012) × 2,47105 → **kg/ha**.

### Limitaciones

- **Origen de los datos.** Son regiones productivas de EE. UU. Sus rendimientos son mayores que el promedio boliviano (soya: mediana de 2.825 kg/ha en la referencia frente a 2.360 kg/ha en Santa Cruz en 2025-2026, según ANAPO) y sus costos responden a otra estructura de precios. No se aplica un factor de calibración: la diferencia se reduce reentrenando con las campañas reales del sistema.
- **Variables disponibles.** Solo se usan variables que existen a la vez en el dataset y en `servicio-gestion`: el cultivo y el costo por hectárea de cada categoría. No hay clima, suelo ni variedad.
- **Cultivos.** Soya, maíz y sorgo. Otro cultivo responde `422 CULTIVO_NO_SOPORTADO`. El nombre del cultivo de gestión se compara sin tildes ni mayúsculas (`Soya`, `soja`, `Maíz`, `maiz duro`, `Sorgo granífero`…).

---

## `rendimiento` — Random Forest Regressor (RF-18, CU-14)

| | |
|---|---|
| Propósito | Estimar el rendimiento (kg/ha) de una campaña a partir de sus costos por hectárea |
| Variables | One-hot del cultivo (`SOYA`, `MAIZ`, `SORGO`) + costo por hectárea de `INSUMO`, `MANO_DE_OBRA`, `MAQUINARIA` y `OTRO` (BOB/ha) |
| Algoritmo | `RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=42)` |
| Validación | `KFold(5, shuffle=True, random_state=42)` con `cross_val_predict`; después se reentrena con todas las filas |
| Intervalo | Percentiles 10 y 90 de las estimaciones de los 300 árboles |
| Métrica principal | MAE (menor es mejor) |

**Versión vigente: 1** (conjunto de referencia, 485 filas ERS, semilla 42).

| Alcance | MAE (kg/ha) | RMSE (kg/ha) | R² |
|---|---|---|---|
| Global | 641,55 | 903,06 | 0,915 |
| Soya | 307,58 | 398,10 | 0,538 |
| Maíz | 1.014,95 | 1.293,75 | 0,522 |
| Sorgo | 647,29 | 780,08 | 0,399 |

Lectura honesta de las métricas: el R² global es alto porque gran parte de la varianza es la diferencia de rendimiento entre cultivos (el maíz rinde unas tres veces más que la soya). **Dentro de cada cultivo el modelo explica alrededor de la mitad de la variación** (R² de 0,40 a 0,54), con un error típico de unos 300 kg/ha en soya. Por eso cada estimación trae su intervalo y la marca de resultado orientativo.

Advertencias de la respuesta:

- `FUERA_DE_RANGO`: algún costo por hectárea es menor que la mitad del mínimo o mayor que el doble del máximo visto en el entrenamiento para ese cultivo. Se estima igual, con menos confianza.

---

## `patrones` — K-Means + Isolation Forest (RF-19, CU-15)

| | |
|---|---|
| Propósito | Agrupar campañas finalizadas por perfil de costo y rendimiento, y detectar las atípicas |
| Perfil | Costo total por hectárea / mediana del cultivo; rendimiento / mediana del cultivo; participación de cada categoría en el costo total. Así campañas de distintos cultivos son comparables |
| Algoritmos | `StandardScaler` → `KMeans(n_init=10, random_state=42)` con `k` de 3 a 6 elegido por silueta → `IsolationForest(contamination=0.05, random_state=42)` |
| Descripción de grupos | Desde el centroide: costo y rendimiento relativos "bajo" (< 0,85), "medio" o "alto" (> 1,15); si dos grupos coinciden, se agrega la categoría de costo con mayor participación |
| Motivos de anomalía | Variables del perfil con \|z\| > 2 respecto de la referencia, redactadas con plantillas fijas (sin modelo de lenguaje) |
| Métrica principal | Silueta (mayor es mejor) |

**Versión vigente: 1** (conjunto de referencia, 485 filas ERS, semilla 42).

| Métrica | Valor |
|---|---|
| `k` elegido | 5 |
| Silueta | 0,276 (k=3: 0,264; k=4: 0,264; k=5: 0,276; k=6: 0,275) |
| Proporción marcada como anómala en el entrenamiento | 5,2 % |

Grupos de la versión 1:

| Grupo | Descripción |
|---|---|
| 0 | Costo bajo · rendimiento bajo |
| 1 | Costo medio · rendimiento medio |
| 2 | Costo medio · rendimiento medio · más insumos |
| 3 | Costo medio · rendimiento medio · más maquinaria |
| 4 | Costo alto · rendimiento medio |

La silueta de 0,28 indica grupos con separación moderada: son perfiles orientativos, no categorías nítidas. Como los modelos se entrenan sobre la referencia, una campaña del sistema recibe grupo y marca de anomalía aunque sea la única finalizada.

---

## Cómo reentrenar y publicar

Dentro del contenedor del servicio (tiene las variables de entorno de Firestore, Cloud Storage, Keycloak y el gateway):

```bash
# 1. (Opcional) regenerar el conjunto de referencia desde el ERS
docker compose exec servicio-ia python -m app.ml.datos.preparar_ers

# 2. Entrenar; con --incluir-historicos suma las campañas finalizadas de servicio-gestion
docker compose exec servicio-ia python -m app.ml.entrenar rendimiento --incluir-historicos
docker compose exec servicio-ia python -m app.ml.entrenar patrones --incluir-historicos

# 3. Revisar las métricas impresas (o GET /api/ia/v1/modelos) y publicar como administrador
curl -X POST "$GATEWAY/api/ia/v1/modelos/rendimiento/versiones/<n>/publicacion" \
  -H "Authorization: Bearer $TOKEN_ADMIN" -H "Content-Type: application/json" \
  -d '{"justificacion": "..."}'   # obligatoria si la métrica principal es peor que la vigente
```

- Cada versión guarda en `gs://<bucket>/modelos/<nombre>/<idEntrenamiento>/` el modelo (`modelo.joblib`), el conjunto exacto usado (`dataset.csv`) y sus metadatos (`metadatos.json`), y en Firestore (`versiones_modelo`) el estado, las métricas y las estadísticas de referencia.
- Con la misma semilla y el mismo conjunto de datos, el entrenamiento da las mismas métricas.
- Las instancias cargan la nueva versión vigente en menos de 60 s sin reiniciarse; la que atiende la publicación, de inmediato.
- Después de publicar, actualizar las tablas de métricas de este documento en el mismo commit.
