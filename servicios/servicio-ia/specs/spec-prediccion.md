# Modelos, predicción de rendimiento y análisis de patrones — `servicio-ia`

| Campo | Valor |
|---|---|
| Servicio | `servicio-ia` |
| Archivo | `specs/spec-prediccion.md` |
| Estado | Implementada (2026-11-05) · pipeline en GitHub pendiente de confirmar |
| Fecha | 2026-11-04 |
| Constitución | v3.1.0 (secciones 1, 4, 5, 7 y 9) |
| Trazabilidad | CU-14, CU-15 · RF-18, RF-19 · RN-13 · proceso 9 y 10 del documento de requisitos · RNF-05 |
| Depende de | `spec-base.md` (cliente del gateway, seguridad, errores) y `spec-trabajos.md` (Firestore). `servicio-gestion`: `GET /campanias/{id}`, `GET /campanias/{id}/costos`, `GET /campanias/{id}/indicadores`, `GET /cultivos/{id}` y `GET /campanias/historicos` (ya implementados) |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## 1.1 Contexto

El documento de requisitos pide estimar el rendimiento con un modelo supervisado "entrenado con datos históricos de campañas proporcionados por Spring Boot" (RF-18, proceso 9) e identificar agrupaciones y anomalías con modelos no supervisados (RF-19, proceso 10).

**Problema:** el sistema es nuevo y `servicio-gestion` no tiene campañas finalizadas. Ningún modelo se entrena con cero filas.

**Solución:** cada modelo se entrena con un **conjunto de referencia** construido a partir de un dataset público, más las campañas finalizadas de `servicio-gestion` cuando existan. Así hay un modelo útil desde el primer día y mejora a medida que se registran campañas reales.

### Dataset público elegido

**USDA ERS — Commodity Costs and Returns** (Servicio de Investigación Económica del Departamento de Agricultura de EE. UU.), archivos `corn.csv`, `soybeans.csv` y `sorghum.csv` de la sección "Recent Cost and Returns" (<https://www.ers.usda.gov/data-products/commodity-costs-and-returns>).

| Criterio | Por qué encaja |
|---|---|
| Cultivos | Maíz, soya y sorgo: exactamente los granos del caso de estudio (§1.2.2 del documento de requisitos) |
| Variables | Rendimiento por superficie sembrada y costos por superficie desglosados (semilla, fertilizante, fitosanitarios, combustible, reparaciones, mano de obra, maquinaria…), que se pueden agrupar en las mismas categorías de `CostoCampania` de `servicio-gestion` (`INSUMO`, `MANO_DE_OBRA`, `MAQUINARIA`, `OTRO`) |
| Cobertura | Una fila por cultivo, región productiva y año, desde 1996-1997 hasta la última actualización: unas 500 filas útiles |
| Formato | CSV en formato largo (`Commodity, Category, Item, Units, Size, Region, Country, Year, Value, Survey base year`) |
| Licencia | Publicación del gobierno federal de EE. UU. (dominio público en EE. UU.). Se cita como "U.S. Department of Agriculture, Economic Research Service. Commodity Costs and Returns data." |

Alternativas descartadas:

| Dataset | Motivo |
|---|---|
| Kaggle "Crop Yield Prediction" (FAO + Banco Mundial, por país y año) | Sus variables (lluvia, temperatura, toneladas de pesticida por país) no existen en el sistema: no se podría predecir una campaña real |
| Kaggle "Agriculture Crop Yield" (1 millón de filas) | Sintético y sin costos |
| ANAPO (Bolivia) | Publica boletines y promedios departamentales, no un dataset descargable por campaña |

Para que sea comparable con las campañas del sistema, el conjunto de referencia convierte las unidades y deflacta los montos (2.3).

**Limitación conocida (RN-13):** los datos son de EE. UU. Sus rendimientos son más altos que el promedio boliviano (soya: unos 3.300 kg/ha frente a 2.360 kg/ha en Santa Cruz en 2025-2026, según ANAPO). Las estimaciones son orientativas, y la brecha se reduce a medida que se agregan campañas reales al entrenamiento. La documentación del modelo lo explica (constitución §5).

### Modelos de esta spec

| Nombre | Algoritmo | Entrada | Salida |
|---|---|---|---|
| `rendimiento` | Random Forest Regressor | Cultivo y costo por hectárea de cada categoría | Rendimiento en kg/ha con intervalo |
| `patrones` | Escalador + K-Means + Isolation Forest | Perfil relativo de costo y rendimiento de una campaña finalizada | Grupo con su descripción y marca de anomalía con sus motivos |

`patrones` agrupa los dos modelos no supervisados en una sola versión porque comparten las variables y el escalador.

## 1.2 Escenarios de usuario y pruebas

### Historia 1 — Estimar el rendimiento de una campaña (Prioridad: P1)

Como gerencia, quiero una estimación del rendimiento de una campaña a partir de sus costos registrados, y compararla con el rendimiento real si ya terminó (CU-14, proceso 9).

**Por qué esta prioridad:** es el caso de uso del modelo supervisado (RF-18).

**Prueba independiente:** con una versión del modelo entrenada sobre `tests/fixtures` y `servicio-gestion` simulado.

**Escenarios de aceptación:**

1. **Dado** una campaña de soya con costos registrados, **cuando** gerencia pide `POST /predicciones` con `idCampania`, **entonces** recibe `201` con:
   - el rendimiento estimado en kg/ha y su intervalo (percentiles 10 y 90 de los árboles);
   - la producción estimada (rendimiento × superficie);
   - los costos por hectárea usados como entrada;
   - la versión del modelo y `orientativo: true` con el aviso de RN-13.
2. **Dado** una campaña `FINALIZADA` con indicadores disponibles, **entonces** la respuesta incluye además el rendimiento real de `servicio-gestion`, sin recalcularlo (constitución §1).
3. **Dado** una campaña `PLANIFICADA` sin costos, **cuando** se envían `costosPorHectarea` en la solicitud, **entonces** la estimación usa esos costos ("estimar el rendimiento de futuras campañas") y lo indica en `origenCostos = SIMULADOS`.
4. **Dado** una campaña sin costos registrados y sin `costosPorHectarea`, **entonces** `422 DATOS_INSUFICIENTES`: nunca se inventa un valor (constitución §5).
5. **Dado** un cultivo que no es soya, maíz ni sorgo, **entonces** `422 CULTIVO_NO_SOPORTADO`, con los cultivos admitidos en `detalles`.
6. **Dado** costos por hectárea fuera del rango visto en el entrenamiento para ese cultivo, **entonces** se estima igual, con la advertencia `FUERA_DE_RANGO` y los campos afectados.
7. **Dado** una campaña inexistente, **entonces** `404 CAMPANIA_NO_ENCONTRADA`; **dado** `servicio-gestion` caído, `503 DEPENDENCIA_NO_DISPONIBLE`.
8. **Dado** que no hay una versión vigente de `rendimiento`, **entonces** `503 MODELO_NO_DISPONIBLE`.
9. **Dado** una estimación hecha, **entonces** queda guardada y `GET /predicciones?idCampania=` la lista, de la más reciente a la más antigua, para gerencia y para el servidor GraphQL.

---

### Historia 2 — Encontrar grupos y campañas atípicas (Prioridad: P1)

Como gerencia, quiero ver en qué perfiles de costo y rendimiento se agrupan las campañas finalizadas, y cuáles se salen de lo normal, para revisarlas (CU-15, proceso 10).

**Prueba independiente:** con una versión de `patrones` entrenada sobre `tests/fixtures` y una lista de históricos simulada que incluye una campaña con costo de insumos muy alto.

**Escenarios de aceptación:**

1. **Dado** campañas finalizadas de soya y maíz, **cuando** gerencia pide `POST /analisis` (con filtros opcionales por cultivo y rango de `fechaFinalizacion`), **entonces** recibe `201` con:
   - los grupos, cada uno con su descripción (por ejemplo, "Costo alto · rendimiento medio"), la cantidad de campañas y sus IDs;
   - las anomalías, cada una con `idCampania`, `nombreParcela`, puntaje y motivos legibles (por ejemplo, "Costo de insumos por hectárea 2,4 veces el típico del cultivo");
   - la versión del modelo y `orientativo: true`.
2. **Dado** una sola campaña finalizada, **entonces** igual recibe su grupo y si es atípica: la comparación es contra el conjunto de referencia, no solo contra las demás campañas del sistema.
3. **Dado** campañas finalizadas sin indicadores (`SIN_COSTOS`) o de cultivos no admitidos, **entonces** se excluyen y se informan en `excluidas` con el motivo.
4. **Dado** ninguna campaña analizable, **entonces** `422 DATOS_INSUFICIENTES`.
5. **Dado** más de 1.000 campañas que cumplen el filtro, **entonces** se analizan las 1.000 más recientes y la respuesta indica `truncado: true`.
6. **Dado** un análisis hecho, **entonces** queda guardado y `GET /analisis/{id}` y `GET /analisis` (el más reciente primero) lo devuelven a gerencia y al servidor GraphQL.

---

### Historia 3 — Entrenar y publicar una versión de un modelo (Prioridad: P1)

Como administrador de TI, quiero entrenar una versión nueva con el conjunto de referencia y las campañas reales, revisar sus métricas y publicarla solo si no es peor que la vigente (constitución §5).

**Prueba independiente:** con el emulador de GCS y Firestore y un dataset pequeño de `tests/fixtures`.

**Escenarios de aceptación:**

1. **Dado** el conjunto de referencia, **cuando** se ejecuta `python -m app.ml.entrenar rendimiento`, **entonces** se crea una versión `CANDIDATA` con:
   - el modelo y el conjunto de datos exacto usado, en Cloud Storage;
   - fecha, variables, hiperparámetros, semilla, métricas (MAE, RMSE y R² por validación cruzada) y la cantidad de filas por origen, en Firestore.
2. **Dado** la opción `--incluir-historicos`, **entonces** el entrenamiento agrega las campañas finalizadas de `servicio-gestion` con indicadores, marcadas con origen `SISTEMA`; si `servicio-gestion` no responde, el entrenamiento falla con un mensaje claro (no entrena a medias).
3. **Dado** el mismo conjunto de datos y la misma semilla, **entonces** dos entrenamientos producen las mismas métricas (reproducibilidad).
4. **Dado** una `CANDIDATA`, **cuando** un administrador la publica, **entonces** pasa a `VIGENTE` y la anterior a `RETIRADA`, en una sola transacción.
5. **Dado** una `CANDIDATA` con la métrica principal peor que la vigente (MAE mayor en `rendimiento`, silueta menor en `patrones`), **entonces** la publicación responde `422 METRICAS_INFERIORES`, salvo que se envíe una `justificacion` (mínimo 20 caracteres), que queda registrada.
6. **Dado** una versión publicada, **entonces** cada instancia del servicio la carga en menos de 90 s sin reiniciar, y las respuestas siguientes informan la nueva versión.
7. **Dado** un usuario sin `administrador`, **entonces** la publicación responde `403 SIN_PERMISO`.
8. **Dado** gerencia o administrador, **entonces** `GET /modelos` lista las versiones con su estado y métricas.

---

### Historia 4 — Preparar el conjunto de referencia de forma reproducible (Prioridad: P2)

Como desarrollador, quiero regenerar el conjunto de referencia desde el dataset público con un solo comando y saber de dónde sale cada fila.

**Escenarios de aceptación:**

1. **Dado** los tres CSV del ERS, **cuando** se ejecuta `python -m app.ml.datos.preparar_ers`, **entonces** se genera `datos/referencia/campanias_referencia.csv` con las columnas de 2.3, y `datos/referencia/fuentes.json` con las URL, la fecha de descarga y el SHA-256 de cada archivo.
2. **Dado** una fila de región con algún costo o el rendimiento faltante, **entonces** se descarta y se cuenta en el resumen.
3. **Dado** el CSV generado, **entonces** está en el repositorio: el entrenamiento no depende de que el sitio del ERS esté disponible.

### Casos borde

- **El nombre del cultivo en `servicio-gestion` varía** ("Soya", "soja", "Maíz", "maiz"): se compara sin tildes ni mayúsculas contra una lista fija de sinónimos (2.4).
- **Campaña `EN_CURSO` con costos parciales:** se estima con los costos registrados hasta el momento, y la respuesta lo indica (`origenCostos = REGISTRADOS`, `estadoCampania = EN_CURSO`).
- **Superficie con 4 decimales:** la producción estimada se redondea a 2 decimales (mitad hacia arriba), como en `servicio-gestion` (D-04 de su README).
- **Dos publicaciones simultáneas:** la transacción de Firestore deja una sola `VIGENTE`.
- **La versión vigente no se puede descargar de GCS al arrancar:** la instancia sigue atendiendo lo que no la usa; predicción o análisis responden `503 MODELO_NO_DISPONIBLE` y readiness lo informa.
- **Históricos con más de 1.000 campañas para entrenar:** el entrenamiento sí las pagina todas; el límite de 1.000 es solo del análisis en línea.

## 1.3 Requisitos

### Requisitos funcionales

#### Modelos y versiones

- **RQ-PRE-01:** toda versión tiene número entero incremental por modelo, estado (`CANDIDATA`, `VIGENTE`, `RETIRADA`), fecha, conjunto de datos (ruta, SHA-256 y filas por origen), variables, hiperparámetros, semilla, métricas y, si aplica, justificación. Es inmutable salvo el estado.
- **RQ-PRE-02:** el entrenamiento se ejecuta por línea de comandos, fuera del ciclo HTTP, y registra la versión como `CANDIDATA`.
- **RQ-PRE-03:** la publicación aplica la regla de métricas de la Historia 3, escenario 5.
- **RQ-PRE-04:** cada instancia carga la versión vigente al arrancar y revisa cada 60 s si cambió.
- **RQ-PRE-05:** toda respuesta de un modelo incluye la versión, `orientativo: true` y el aviso de RN-13.

#### Rendimiento

- **RQ-PRE-06:** `POST /predicciones` estima con los costos registrados de la campaña o con `costosPorHectarea` simulados.
- **RQ-PRE-07:** sin costos → `422 DATOS_INSUFICIENTES`; cultivo no admitido → `422 CULTIVO_NO_SOPORTADO`; entrada fuera de rango → advertencia `FUERA_DE_RANGO`.
- **RQ-PRE-08:** si la campaña está `FINALIZADA`, se agrega el rendimiento real de `servicio-gestion`.
- **RQ-PRE-09:** cada predicción se guarda en `predicciones` y se puede listar por campaña.

#### Patrones

- **RQ-PRE-10:** `POST /analisis` toma los históricos de `servicio-gestion` (como máximo los 1.000 más recientes), asigna grupo y marca de anomalía con la versión vigente de `patrones` y explica los motivos.
- **RQ-PRE-11:** cada análisis se guarda en `analisis` y se puede consultar por ID y listar.

#### Conjunto de referencia

- **RQ-PRE-12:** el conjunto de referencia se genera con un comando reproducible y se versiona en el repositorio con sus fuentes.

### Entidades clave

| Entidad | Colección | Campos principales |
|---|---|---|
| `VersionModelo` | `versiones_modelo` (ID `<nombre>-<version>`) | `nombre`, `version`, `estado`, `fechaEntrenamiento`, `fechaPublicacion`, `dataset`, `variables`, `hiperparametros`, `semilla`, `metricas`, `referencia` (rangos y medianas por cultivo), `justificacion`, `rutaArtefactos` |
| `PrediccionRendimiento` | `predicciones` | `id`, `idCampania`, `idSolicitante`, `fecha`, `versionModelo`, `cultivo`, `estadoCampania`, `origenCostos`, `costosPorHectarea`, `rendimientoEstimado`, `intervalo`, `produccionEstimada`, `rendimientoReal`, `advertencias` |
| `Analisis` | `analisis` | `id`, `idSolicitante`, `fecha`, `versionModelo`, `filtros`, `grupos`, `anomalias`, `excluidas`, `cantidadAnalizadas`, `truncado` |

## 1.4 Permisos

| Operación | Roles |
|---|---|
| `POST /predicciones`, `POST /analisis` | `gerencia` |
| `GET /predicciones`, `GET /analisis`, `GET /analisis/{id}` | `gerencia`, `lectura_ia` (cuenta de servicio de GraphQL) |
| `GET /modelos` | `administrador`, `gerencia` |
| `POST /modelos/{nombre}/versiones/{version}/publicacion` | `administrador` |

`lectura_ia` es un rol de realm nuevo, asignado solo a la cuenta de servicio `graphql-server` ("lectura de resultados para integración", constitución §9). Se agrega al realm en esta spec (2.11).

## 1.5 Errores de esta funcionalidad

| HTTP | Código | Mensaje | Cuándo |
|---|---|---|---|
| 400 | `DATOS_INVALIDOS` | (común) | Formato o filtros inválidos |
| 404 | `CAMPANIA_NO_ENCONTRADA` | "La campaña no existe." | La reporta `servicio-gestion` |
| 404 | `ANALISIS_NO_ENCONTRADO` | "El análisis solicitado no existe." | `GET /analisis/{id}` |
| 404 | `VERSION_MODELO_NO_ENCONTRADA` | "La versión del modelo no existe." | Publicación |
| 409 | `VERSION_NO_PUBLICABLE` | "Solo se puede publicar una versión candidata." | Publicar una `VIGENTE` o `RETIRADA` |
| 422 | `DATOS_INSUFICIENTES` | "No hay datos suficientes para realizar la estimación." | Historia 1, escenario 4; Historia 2, escenario 4 |
| 422 | `CULTIVO_NO_SOPORTADO` | "El modelo no admite este cultivo." | Historia 1, escenario 5 |
| 422 | `METRICAS_INFERIORES` | "Las métricas de la versión son peores que las de la vigente. Indique una justificación para publicarla." | Historia 3, escenario 5 |
| 503 | `MODELO_NO_DISPONIBLE` | "El modelo solicitado no está disponible en este momento." | No hay versión vigente o no se pudo cargar |
| 503 | `DEPENDENCIA_NO_DISPONIBLE` | (común) | `servicio-gestion`, Firestore o GCS no disponibles |

## 1.6 Criterios de éxito

- **CE-PRE-01:** los escenarios de las historias 1 a 4 pasan como tests automáticos.
- **CE-PRE-02:** `POST /predicciones` responde en menos de 3 s (RNF-05) con `servicio-gestion` respondiendo normalmente.
- **CE-PRE-03:** `POST /analisis` con 1.000 campañas responde en menos de 5 s.
- **CE-PRE-04:** la primera versión de `rendimiento` entrenada con el conjunto de referencia tiene R² ≥ 0,6 en validación cruzada. Si no se alcanza, se documenta el valor obtenido y se publica con justificación (es un umbral de referencia, no una garantía).
- **CE-PRE-05:** la documentación del modelo (`docs/modelos.md`) describe variables, fuentes, transformaciones, métricas de la versión vigente, la limitación de origen de los datos y cómo reentrenar (constitución §5).
- **CE-PRE-06:** cobertura ≥ 80 % (README D-13), Ruff y mypy sin errores, pipeline en verde.

## 1.7 Supuestos

- Las campañas reales registran sus costos en bolivianos con las mismas cuatro categorías (`servicio-gestion`, D-01 de su README) y su producción en kg (D-03).
- El tipo de cambio oficial del boliviano es fijo (6,96 BOB por USD) desde 2011; se usa ese valor.
- Los archivos del ERS se actualizan una vez al año. El CSV generado queda en el repositorio, así que una actualización del ERS no cambia nada hasta que se regenere a propósito.

## 1.8 Aclaraciones

- **AC-01 — ¿Por qué no se calibran los rendimientos de EE. UU. a Bolivia?** Habría que inventar un factor de ajuste por cultivo con otra fuente (FAOSTAT) y la estimación dejaría de ser trazable a un dato publicado. Se prefiere mostrar la limitación y dejar que las campañas reales (`--incluir-historicos`) corrijan el modelo.
- **AC-02 — ¿Por qué solo costos y cultivo como variables?** Son las únicas que existen a la vez en el dataset público y en `servicio-gestion`. Variables como lluvia o tipo de suelo no están en el sistema, y un modelo que las use no podría estimar una campaña real.
- **AC-03 — ¿Por qué los no supervisados se comparan contra la referencia?** Con pocas campañas en el sistema, agrupar solo entre ellas no tiene sentido (3 campañas no forman grupos). Entrenados sobre la referencia, los modelos asignan grupo y detectan anomalías aunque haya una sola campaña.
- **AC-04 — ¿Por qué el análisis es síncrono y no un trabajo?** Con 1.000 campañas, leer dos páginas de históricos y aplicar modelos ya cargados toma pocos segundos, dentro del tiempo límite del gateway (10 s).
- **AC-05 — ¿Por qué los costos se deflactan?** Los montos del ERS van de 1996 a 2025 en dólares corrientes. Sin deflactar, el modelo confundiría inflación con más inversión.

## 1.9 Fuera de alcance

- Entrenamiento disparado desde la API o programado (se ejecuta a mano con el comando).
- Predicción por parcela o por lote de campañas.
- Variables climáticas o de suelo.
- Calibración a rendimientos bolivianos (AC-01).

---

# 2. Plan

Criterio general: lo mínimo que cumple la spec y la constitución. Reutiliza la base y el cliente de Firestore de `spec-trabajos.md`.

**Documentos que debe tener a mano quien implemente:** la constitución, `specs/README.md`, `spec-base.md`, `spec-trabajos.md`, este archivo y las specs de `servicio-gestion` citadas en "Depende de".

## 2.1 Dependencias

| Dependencia | Para qué |
|---|---|
| `scikit-learn` | Random Forest, K-Means, Isolation Forest, escalador y validación cruzada (constitución §2) |
| `pandas`, `numpy` | Preparación del conjunto de referencia y de las variables |
| `joblib` | Serialización de los modelos |
| `google-cloud-storage` | Artefactos de modelos y conjuntos de datos. Usa el emulador si existe `STORAGE_EMULATOR_HOST` |

## 2.2 Configuración

| Variable | Obligatoria | Uso | Valor local |
|---|---|---|---|
| `GCS_BUCKET` | Sí | Bucket de artefactos | Ya en Docker Compose (`ia-artefactos`) |
| `STORAGE_EMULATOR_HOST` | No | Lo lee la librería; vacío en la nube | Ya en Docker Compose |
| `MODELOS_INTERVALO_REVISION_SEGUNDOS` | No (60) | Revisión de la versión vigente | — |

## 2.3 Conjunto de referencia (`app/ml/datos/preparar_ers.py`)

Entrada: los tres CSV del ERS (URL fijas en el script). Salida: `datos/referencia/campanias_referencia.csv` y `datos/referencia/fuentes.json`, en la raíz del servicio, fuera de `app/`.

Pasos:

1. Descargar los CSV a una carpeta temporal y registrar URL, fecha y SHA-256 en `fuentes.json`.
2. Filtrar: `Region` distinta de `U.S. total` (es un agregado de las demás); `Size` igual a todas las explotaciones; `Units` `dollars per planted acre` o `bushels per planted acre`.
3. Pasar a una fila por cultivo, región y año y agrupar los ítems:

   | Categoría | Ítems del ERS |
   |---|---|
   | `INSUMO` | Seed, Fertilizer, Chemicals |
   | `MAQUINARIA` | Custom services; Fuel, lube, and electricity; Repairs; Capital recovery of machinery and equipment |
   | `MANO_DE_OBRA` | Hired labor |
   | `OTRO` | Purchased irrigation water; Interest on operating capital; Taxes and insurance; General farm overhead |
   | Se excluyen | Opportunity cost of land; Opportunity cost of unpaid labor (costos implícitos que un productor no registra como gasto) |

   Nombres verificados en los CSV (2026-11-05): algunos ítems traen espacios al final (`"Fertilizer  "`, `"Custom services  "`), así que se comparan sin espacios; en sorgo el interés se llama `Interest on operating inputs` (equivale a `Interest on operating capital`). `Size` siempre es `No specific size` (no se filtra). Años: maíz 1996-2025, soya 1997-2025, sorgo 1995-2025. Resultado: 485 filas (maíz 180, soya 203, sorgo 102), sin descartes.
4. Deflactar los montos a dólares del último año del dataset con el IPC de EE. UU. (BLS CPI-U, serie `CUUR0000SA0`, promedio anual), guardado como tabla pequeña en `datos/referencia/ipc_eeuu.csv` con su fuente. Los valores se obtuvieron de la API pública del BLS (`api.bls.gov/publicAPI/v2`, campo `M13`), porque el servidor de archivos del BLS rechaza descargas automáticas; 2025 tiene promedio anual aunque falta octubre (cierre del gobierno).
5. Convertir:
   - costos: USD por acre × 2,47105 (acres por hectárea) × 6,96 (BOB por USD) → BOB/ha, 2 decimales;
   - rendimiento: bushels por acre × kg por bushel (soya 27,2155; maíz y sorgo 25,4012) × 2,47105 → kg/ha, 2 decimales.
6. Descartar las filas con algún valor faltante y escribir el resumen (filas por cultivo, descartadas).

Columnas del CSV: `origen` (`ERS`), `cultivo` (`SOYA`, `MAIZ`, `SORGO`), `region`, `anio`, `costoInsumoHa`, `costoManoDeObraHa`, `costoMaquinariaHa`, `costoOtroHa`, `rendimientoHa`.

## 2.4 Variables (`prediccion/variables.py`)

Lo usan el entrenamiento y la inferencia. Va en `prediccion/` y `ml/` lo importa: nada del código HTTP importa `ml/`, pero `ml/` puede importar los módulos (constitución v3.1.0 §3).

- `normalizar_cultivo(nombre) -> Cultivo | None`: sin tildes, minúsculas y espacios recortados; `soya`, `soja` → `SOYA`; `maiz`, `maiz amarillo`, `maiz duro` → `MAIZ`; `sorgo`, `sorgo granifero` → `SORGO`. Si el nombre completo no es un sinónimo, se usa la primera palabra ("Soya Munasqa", "Maíz amarillo duro"): una variedad no cambia el cultivo. Se agregó al probar con los cultivos reales de `servicio-gestion`, que tienen nombres como "Soya E2E 2515f4b4".
- `vector_rendimiento(cultivo, costos_ha) -> list[float]`: one-hot del cultivo + los cuatro costos por hectárea.
- `perfil_patrones(cultivo, costos_ha, rendimiento_ha, referencia) -> list[float]`: costo total por hectárea / mediana del cultivo, rendimiento / mediana del cultivo, y la participación de cada categoría en el costo total. Así el perfil es comparable entre cultivos.
- `fuera_de_rango(cultivo, costos_ha, referencia) -> list[str]`: campos menores que la mitad del mínimo o mayores que el doble del máximo del cultivo en el entrenamiento.

`referencia` (medianas, mínimos y máximos por cultivo) se calcula al entrenar y se guarda en los metadatos de la versión.

## 2.5 Entrenamiento (`app/ml/entrenar.py`)

`python -m app.ml.entrenar {rendimiento|patrones} [--incluir-historicos] [--semilla 42]`:

1. Carga `campanias_referencia.csv`. Con `--incluir-historicos`, pagina `GET /api/gestion/v1/campanias/historicos?tamanio=500` con el cliente de `spec-base.md`, convierte los decimales de texto a `Decimal` y luego a `float`, y agrega las campañas con `rendimientoPorHectarea` y cultivo admitido, con origen `SISTEMA`. Calcula los costos por hectárea como `costosPorCategoria / superficieHectareas`.
2. **`rendimiento`:** `RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=semilla)`. Métricas con `KFold(5, shuffle=True, random_state=semilla)`: MAE, RMSE y R², en promedio y por cultivo. Se reentrena con todas las filas.
3. **`patrones`:** `StandardScaler` sobre el perfil. `KMeans(n_init=10, random_state=semilla)` con `k` entre 3 y 6, eligiendo la mayor silueta. `IsolationForest(contamination=0.05, random_state=semilla)`. Descripción de cada grupo desde su centroide (en la escala original): costo relativo y rendimiento relativo "bajo" (< 0,85), "medio" o "alto" (> 1,15), por ejemplo "Costo alto · rendimiento medio". Métrica principal: silueta; también la proporción marcada como anómala.
4. Sube a `gs://<bucket>/modelos/<nombre>/<idEntrenamiento>/` `modelo.joblib`, `dataset.csv` y `metadatos.json`, y después registra `VersionModelo` en Firestore como `CANDIDATA`, con `version` = última + 1 (en transacción). La carpeta usa un UUID propio del entrenamiento y no el número de versión: el número recién se conoce al registrar, y subir primero evita una versión registrada sin sus archivos.
5. Imprime las métricas y la comparación con la vigente.

## 2.6 Módulo `modelos/`

- **`integracion/almacen_archivos.py`:** `Protocol AlmacenArchivos` (`subir(ruta, datos, tipo)`, `descargar(ruta) -> bytes`) y `AlmacenGcs`. Es uno de los bordes de la constitución §3; las specs de visión y reportes lo reutilizan.
- **`integracion/repositorio_versiones.py`:** `RepositorioVersionesFirestore` sobre Firestore (`versiones_modelo`), con documentos en camelCase que `modelos/` convierte en `VersionModelo`. También `integracion/repositorio_resultados.py` para `predicciones` y `analisis`. Firestore es un borde externo y vive en `integracion/` (constitución §3): `registrar_candidata`, `obtener`, `listar(nombre)`, `vigente(nombre)` y `publicar(nombre, version, justificacion)`, que en una transacción verifica `CANDIDATA`, retira la vigente y marca la nueva.
- **`modelos/reglas.py`** (funciones puras): `puede_publicar(candidata, vigente, justificacion)` con la métrica principal y su sentido (`MAE` menor es mejor; `silueta` mayor es mejor).
- **`modelos/cargador.py`:** `CargadorModelos` en `app.state`. Al arrancar y cada `MODELOS_INTERVALO_REVISION_SEGUNDOS`, consulta la vigente de cada modelo registrado; si cambió, descarga y deserializa con `joblib` en un hilo (`asyncio.to_thread`) y reemplaza la referencia en memoria de una sola vez. `obtener(nombre) -> ModeloCargado` (modelo, versión, referencia) o `503 MODELO_NO_DISPONIBLE`. *Cambio en spec-vision.md (2026-11-05):* tras publicar, la instancia que atiende la publicación revisa ese modelo en segundo plano (`revisar_en_segundo_plano`) en lugar de esperar la carga antes de responder. Un candado por modelo evita cargas duplicadas.
- Salud: una comprobación **informativa** por modelo (`modelo_rendimiento`, `modelo_patrones`), `UP` si está `CARGADO` y `DOWN` si está `SIN_PUBLICAR` o en `ERROR` (el detalle queda en el log). No es crítica: si se marcara crítica, una instalación nueva sin versiones publicadas nunca estaría lista (constitución §11 pide informar los modelos cargados; RNF-08).
- **`modelos/router.py`:** `GET /modelos?nombre=` y `POST /modelos/{nombre}/versiones/{version}/publicacion` con `{ "justificacion": "..." }` opcional.

## 2.7 Módulo `prediccion/`

- **`integracion/datos_agricolas.py`:** `Protocol DatosAgricolas` (borde externo; la constitución §3 pide declararlo en `integracion/`) y su adaptador `DatosAgricolasGateway` sobre `ClienteGateway`:

  | Método | Llamadas |
  |---|---|
  | `campania_para_prediccion(id)` | `GET /campanias/{id}` (superficie, estado, `idCultivo`), `GET /cultivos/{idCultivo}` (nombre), `GET /campanias/{id}/costos?tamanio=1` (`subtotalesPorCategoria`) y, si está `FINALIZADA`, `GET /campanias/{id}/indicadores` |
  | `historicos(filtros, maximo)` | `GET /campanias/historicos` paginado de 500 en 500 hasta `maximo` |

  El adaptador deja pasar `ErrorServicioRemoto`; `prediccion/servicio.py` traduce un `NO_ENCONTRADO` con `CAMPANIA_NO_ENCONTRADA` a `404 CAMPANIA_NO_ENCONTRADA`. Las cuatro llamadas de una predicción se hacen en paralelo donde no dependen entre sí, para cumplir CE-PRE-02.
- **`prediccion/servicio.py`:**
  - `estimar(id_campania, costos_simulados, solicitante)`: obtiene la campaña, normaliza el cultivo, elige los costos (simulados o registrados ÷ superficie), aplica las reglas de RQ-PRE-07, predice con el modelo cargado (en un hilo) y calcula el intervalo con los percentiles 10 y 90 de `estimators_`, la producción estimada y las advertencias. Guarda en `predicciones`.
  - `analizar(filtros, solicitante)`: obtiene hasta 1.000 históricos, separa los excluidos, arma los perfiles, aplica el escalador, K-Means (grupo) e Isolation Forest (`decision_function` como puntaje; anómala si `predict == -1`). Los motivos de cada anomalía son las variables del perfil con |z| > 2 respecto de la referencia, redactadas con plantillas fijas (sin modelo de lenguaje). Guarda en `analisis`.
- **`prediccion/router.py`:** los endpoints de 2.8.
- Los montos y rendimientos se responden como texto decimal (README D-03) con 2 decimales.

## 2.8 Endpoints

Prefijo `/api/ia/v1`.

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /predicciones` | `gerencia` | `201` + predicción | 400, 401, 403, 404 `CAMPANIA_NO_ENCONTRADA`, 422 `DATOS_INSUFICIENTES` o `CULTIVO_NO_SOPORTADO`, 503 `MODELO_NO_DISPONIBLE` o `DEPENDENCIA_NO_DISPONIBLE` |
| `GET /predicciones?idCampania=&pagina=&tamanio=` | `gerencia`, `lectura_ia` | `200` + página | 400, 401, 403, 503 |
| `POST /analisis` | `gerencia` | `201` + análisis | 400, 401, 403, 422 `DATOS_INSUFICIENTES`, 503 |
| `GET /analisis?pagina=&tamanio=` | `gerencia`, `lectura_ia` | `200` + página (sin el detalle de grupos y anomalías) | 400, 401, 403, 503 |
| `GET /analisis/{id}` | `gerencia`, `lectura_ia` | `200` + análisis | 401, 403, 404 `ANALISIS_NO_ENCONTRADO`, 503 |
| `GET /modelos?nombre=` | `administrador`, `gerencia` | `200` + lista | 400, 401, 403, 503 |
| `POST /modelos/{nombre}/versiones/{version}/publicacion` | `administrador` | `200` + versión | 400, 401, 403, 404 `VERSION_MODELO_NO_ENCONTRADA`, 409 `VERSION_NO_PUBLICABLE`, 422 `METRICAS_INFERIORES`, 503 |

Paginación de listados: `pagina` (desde 0) y `tamanio` (por defecto 20, máximo 100); respuesta `{ items, pagina, tamanio, total }`, igual que `servicio-gestion` (D-05 de su README).

**Solicitud de predicción:**

```json
{
  "idCampania": "uuid",
  "costosPorHectarea": {
    "INSUMO": "2100.00", "MANO_DE_OBRA": "350.00", "MAQUINARIA": "900.00", "OTRO": "150.00"
  }
}
```

`costosPorHectarea` es opcional; si se envía, deben venir las cuatro categorías.

**Respuesta de predicción:**

```json
{
  "id": "uuid",
  "idCampania": "uuid",
  "fecha": "2026-11-04T12:00:00Z",
  "cultivo": "SOYA",
  "estadoCampania": "EN_CURSO",
  "origenCostos": "REGISTRADOS",
  "costosPorHectarea": { "INSUMO": "2100.00", "MANO_DE_OBRA": "350.00", "MAQUINARIA": "900.00", "OTRO": "150.00" },
  "rendimientoEstimado": "3120.40",
  "intervalo": { "minimo": "2810.00", "maximo": "3390.75" },
  "produccionEstimada": "79570.20",
  "rendimientoReal": null,
  "unidad": "kg/ha",
  "advertencias": [],
  "versionModelo": { "nombre": "rendimiento", "version": 1 },
  "orientativo": true,
  "aviso": "Estimación orientativa basada en datos de referencia. No sustituye una evaluación técnica agrícola."
}
```

**Solicitud de análisis:** `{ "idCultivo": "uuid", "fechaFinalizacionDesde": "2025-01-01", "fechaFinalizacionHasta": "2026-12-31" }` (todos opcionales).

**Respuesta de análisis:**

```json
{
  "id": "uuid",
  "fecha": "2026-11-04T12:00:00Z",
  "filtros": { },
  "cantidadAnalizadas": 12,
  "truncado": false,
  "grupos": [
    { "grupo": 0, "descripcion": "Costo alto · rendimiento medio", "cantidad": 4, "idsCampania": ["uuid"] }
  ],
  "anomalias": [
    {
      "idCampania": "uuid",
      "nombreParcela": "Lote Norte",
      "cultivo": "MAIZ",
      "puntaje": "-0.12",
      "motivos": ["Costo de insumos por hectárea 2,4 veces el típico del cultivo"]
    }
  ],
  "excluidas": [ { "idCampania": "uuid", "motivo": "SIN_COSTOS" } ],
  "versionModelo": { "nombre": "patrones", "version": 1 },
  "orientativo": true,
  "aviso": "Agrupaciones y anomalías orientativas. No sustituyen una evaluación técnica agrícola."
}
```

## 2.9 Firestore

| Colección | Índices compuestos (`firestore.indexes.json`) |
|---|---|
| `versiones_modelo` | `nombre` + `version` desc; `nombre` + `estado` |
| `predicciones` | `idCampania` + `fecha` desc |
| `analisis` | `fecha` desc (simple) |

Sin TTL: las predicciones y los análisis son pocos y los consulta GraphQL como historial.

## 2.10 Documentación del modelo

`docs/modelos.md` en la raíz del servicio, con una sección por modelo: propósito, fuentes y licencia, transformaciones (2.3), variables (2.4), algoritmo e hiperparámetros, métricas de la versión vigente, limitaciones (origen de los datos, RN-13) y pasos para reentrenar y publicar. Se actualiza en el mismo commit que publica una versión (constitución §5).

## 2.11 Realm de Keycloak (cambio fuera del servicio)

- `docker/keycloak/realms/realm-agro.json`: rol de realm `lectura_ia` y asignación a la cuenta de servicio `graphql-server`. Su audiencia `servicio-ia` ya existe.
- `specs/spec-keycloak-realm.md`: se agrega `lectura_ia` a RQ-KC-02 y a la tabla de cuentas de servicio, y se borra la nota de permisos pendientes de `servicio-ia` para GraphQL (la de n8n sigue pendiente hasta `spec-reportes.md`).
- Es un cambio en otro componente y se hace en su propio commit.

## 2.12 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `tests/unit/ml/test_preparar_ers.py` | Con un CSV pequeño en formato ERS: filtros, agrupación por categoría, deflactación, conversiones de unidades, descarte de filas incompletas (Historia 4) |
| Unitario | `tests/unit/prediccion/test_variables.py` | Sinónimos de cultivo, vector, perfil, `fuera_de_rango` |
| Unitario | `tests/unit/modelos/test_reglas.py` | `puede_publicar` en los dos sentidos de métrica, con y sin justificación, primera versión |
| Unitario | `tests/unit/ml/test_entrenar.py` | Con `tests/fixtures/referencia_pequena.csv`: métricas registradas, reproducibilidad con la misma semilla, descripción de grupos, `--incluir-historicos` con gestión simulada y caída |
| Unitario | `tests/unit/prediccion/test_servicio.py` | Historia 1 y Historia 2 con `DatosAgricolas` y repositorios simulados y un modelo entrenado en el fixture |
| Integración | `tests/integration/modelos/test_versiones.py` | Con los emuladores: registrar, publicar, publicación concurrente, `METRICAS_INFERIORES`, recarga en `CargadorModelos` |
| Integración | `tests/integration/prediccion/test_router_prediccion.py` | Endpoints de 2.8 con permisos (incluido `lectura_ia`), códigos de error, formato decimal y OpenAPI |
| Integración | `tests/integration/prediccion/test_rendimiento.py` | CE-PRE-02 y CE-PRE-03 con gestión simulada |

---

# 3. Tareas

Cada tarea se da por terminada solo con sus tests en verde. Las marcadas con **[P]** pueden hacerse en paralelo con la anterior.

- [x] **T01** — Agregar las dependencias y variables de 2.1 y 2.2. Implementar `app/ml/datos/preparar_ers.py` y `ipc_eeuu.csv`; generar y versionar `campanias_referencia.csv` y `fuentes.json`. *Hecho cuando:* pasa `test_preparar_ers.py` y el resumen muestra filas de los tres cultivos.
- [x] **T02** — Implementar `prediccion/variables.py`. *Hecho cuando:* pasa `test_variables.py`.
- [x] **T03** — Implementar `AlmacenGcs`, `modelos/repositorio.py` y `modelos/reglas.py`. *Hecho cuando:* pasan `test_reglas.py` y la parte de registro y publicación de `test_versiones.py`.
- [x] **T04** — Implementar `app/ml/entrenar.py`. *Hecho cuando:* pasa `test_entrenar.py`.
- [x] **T05** — Implementar `modelos/cargador.py`, su comprobación de salud y `modelos/router.py`. *Hecho cuando:* pasa `test_versiones.py` completo.
- [x] **T06** — Implementar `prediccion/datos_gestion.py` (contra el contrato real de `servicio-gestion`) y `prediccion/servicio.py`. *Hecho cuando:* pasa `test_servicio.py`.
- [x] **T07** — Implementar `prediccion/router.py` y los índices de `firestore.indexes.json`. *Hecho cuando:* pasan `test_router_prediccion.py` y `test_rendimiento.py`.
- [x] **T08** [P] — Cambiar el realm (2.11) en su propio commit. *Hecho cuando:* un token de `graphql-server` trae `lectura_ia` y lee `GET /predicciones` a través del gateway. Hecho (2026-11-05): `lectura_ia` en `realm-agro.json`, `scripts/verificar-realm.py` y `specs/spec-keycloak-realm.md`; en el Keycloak local se aplicó con la API de administración (crear el rol y asignarlo a la cuenta de `graphql-server`) para no borrar el realm. `verificar-realm.py`: 57 correctas. El token de `graphql-server` trae `lectura_ia` y lee `GET /predicciones` a través del gateway (`200`).
- [x] **T09** — Entrenar y publicar la versión 1 de `rendimiento` y `patrones` en el entorno local, y escribir `docs/modelos.md` con sus métricas. *Hecho cuando:* se cumplen CE-PRE-04 y CE-PRE-05, y una predicción real de una campaña de prueba de `servicio-gestion` responde a través del gateway; se anota el resultado en esta tarea. Hecho (2026-11-05), con Docker Compose y el perfil `backend`: versión 1 de `rendimiento` (MAE 641,55 kg/ha; R² 0,915 global y 0,40 a 0,54 por cultivo) y de `patrones` (k = 5, silueta 0,276), entrenadas con `--incluir-historicos` (gestión no tenía campañas finalizadas: 0 filas `SISTEMA`) y publicadas por el gateway con `admin.prueba`; readiness muestra los dos modelos en `UP`. Con `gerencia.prueba` a través del gateway: predicción de una campaña real de soya en `201` en unos 0,26 s, con `FUERA_DE_RANGO` porque sus costos de prueba son casi nulos; costos simulados en `201`; una campaña de cultivo no admitido en `422 CULTIVO_NO_SOPORTADO`; análisis en `422 DATOS_INSUFICIENTES` (no hay campañas finalizadas; el análisis con 1.000 campañas se cubre en `test_router_prediccion.py`). CE-PRE-04: el R² global supera 0,6; por cultivo no, y queda documentado en `docs/modelos.md`.
