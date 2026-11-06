# Herramientas MCP y agentes inteligentes — `servicio-ia`

| Campo | Valor |
|---|---|
| Servicio | `servicio-ia` |
| Archivo | `specs/spec-agentes.md` |
| Estado | Implementada (2026-11-05) · pipeline en verde |
| Fecha | 2026-11-04 |
| Constitución | v3.1.0 (secciones 1, 3, 6, 7, 8 y 9) |
| Trazabilidad | CU-17 · RF-23 · RN-14 · RNF-08 · §1.7.6 del documento de requisitos ("agentes de monitoreo de campañas, inventario, análisis y reportes") |
| Depende de | `spec-base.md` (cliente del gateway), `spec-trabajos.md` (tipo `CONSULTA_AGENTE`). Endpoints de lectura ya implementados de `servicio-gestion`, `servicio-inventario` y `servicio-operaciones` (2.3) |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## 1.1 Contexto

Gerencia hace una pregunta en lenguaje natural ("¿Qué campañas de soya tienen el costo por hectárea más alto?", "¿Qué insumos están bajo el mínimo?") y recibe una respuesta redactada, con los datos que la respaldan (CU-17).

Tres piezas, con responsabilidades separadas (RN-14):

| Pieza | Qué hace | Qué no hace |
|---|---|---|
| **Herramientas MCP** (`mcp_server/`) | Consultan los microservicios por el gateway, solo lectura, y devuelven datos acotados | No redactan ni calculan cifras nuevas |
| **Agentes** (`agentes/`, LangGraph) | Deciden qué herramientas llamar, con qué parámetros, y en qué orden | No escriben en ningún servicio (no existen herramientas de escritura) |
| **Modelo de lenguaje** (Ollama) | Interpreta la pregunta y redacta la respuesta con los datos recibidos | No es fuente de cifras: toda cifra del texto se verifica contra los datos (constitución §6) |

Agentes de esta spec:

| Agente | Responde sobre | Herramientas |
|---|---|---|
| `campanias` (monitoreo de campañas) | Parcelas, cultivos, campañas, costos, producción, indicadores, labores e incidencias | Gestión y operaciones |
| `inventario` | Insumos, stock, nivel mínimo y consumo en labores | Inventario y labores |

El agente de **reportes** lo agrega `spec-reportes.md`: usa las mismas herramientas y la misma verificación, pero arma tablas para PDF y Excel.

## 1.2 Escenarios de usuario y pruebas

### Historia 1 — Preguntar y recibir una respuesta con sus datos (Prioridad: P1)

Como gerencia, quiero hacer una pregunta sobre campañas o inventario y recibir una respuesta en español con las cifras que la respaldan, sin navegar pantallas (CU-17).

**Por qué esta prioridad:** es el caso de uso de los agentes y la demostración de LangGraph, MCP y Ollama (RF-23).

**Prueba independiente:** con un modelo de lenguaje simulado que sigue un guion (qué herramienta pedir y qué texto redactar) y los microservicios simulados.

**Escenarios de aceptación:**

1. **Dado** la pregunta "¿Qué insumos están bajo el mínimo?", **cuando** gerencia la envía a `POST /consultas-agente`, **entonces** recibe `202` con el trabajo; al terminar, el `resultado` trae:
   - `respuesta`: el texto redactado;
   - `agente`: `inventario`;
   - `herramientas`: cada llamada con nombre, argumentos, duración y si falló;
   - `datos`: el resultado de cada herramienta, tal como lo devolvió;
   - `cifrasOmitidas`: cuántas oraciones se quitaron por tener cifras sin respaldo;
   - el modelo de lenguaje usado y el aviso de RN-14.
2. **Dado** una pregunta sobre campañas, **entonces** responde el agente `campanias` con herramientas de gestión u operaciones.
3. **Dado** una pregunta fuera del dominio ("¿Quién ganó el partido?"), **entonces** el trabajo termina `COMPLETADO` con `agente = fuera_de_alcance` y una respuesta fija que explica qué se puede preguntar, sin llamar herramientas.
4. **Dado** una pregunta vacía o de más de 1.000 caracteres, **entonces** `400 DATOS_INVALIDOS` sin crear el trabajo.
5. **Dado** un usuario sin `gerencia`, **entonces** `403 SIN_PERMISO`.

---

### Historia 2 — Ninguna cifra inventada (Prioridad: P1)

Como gerencia, quiero que toda cifra de la respuesta salga de los datos del sistema, para confiar en ella (RN-14, constitución §6).

**Prueba independiente:** con un modelo simulado que redacta a propósito una cifra que no está en los datos.

**Escenarios de aceptación:**

1. **Dado** una respuesta cuyas cifras están todas en los datos de las herramientas (o en la pregunta), **entonces** se devuelve completa y `cifrasOmitidas = 0`.
2. **Dado** una oración con una cifra que no está en los datos (por ejemplo, un promedio calculado por el modelo), **entonces** esa oración se quita y `cifrasOmitidas` la cuenta.
3. **Dado** que se quitan todas las oraciones, **entonces** `respuesta` es "No pude redactar una respuesta con cifras verificables. Revise los datos consultados." y `datos` sigue disponible.
4. **Dado** cifras escritas en otro formato que el de los datos ("38.250,00", "38250", "38 250 Bs" para `"38250.00"`; "3.000 kg/ha" para `"3000.00"`; "20" o "20.000 litros" para un stock `"20.000"`), **entonces** se reconocen como la misma cifra.
5. **Dado** fechas, años e IDs presentes en los datos, **entonces** sus números no se cuentan como cifras sin respaldo.

---

### Historia 3 — Terminar siempre, aunque el modelo falle (Prioridad: P1)

Como gerencia, quiero un error claro si el modelo de lenguaje no responde o el agente se enreda, nunca una espera indefinida (constitución §6).

**Escenarios de aceptación:**

1. **Dado** que Ollama no responde, **cuando** se envía una consulta, **entonces** `503 MODELO_LENGUAJE_NO_DISPONIBLE` sin crear el trabajo (si ya se sabe que está caído) o el trabajo termina `FALLIDO` con ese código (si cae durante la consulta).
2. **Dado** un agente que pide herramientas sin parar, **cuando** llega a 6 llamadas, **entonces** redacta con lo que tiene; si el grafo llega a 12 pasos, el trabajo termina `FALLIDO` con `LIMITE_PASOS_AGENTE`.
3. **Dado** una consulta que pasa los 120 s, **entonces** `FALLIDO` con `TIEMPO_AGOTADO` (`spec-trabajos.md`).
4. **Dado** una herramienta que falla porque un servicio está caído, **entonces** el agente recibe el error como resultado de la herramienta ("servicio-inventario no disponible") y la respuesta lo dice; no se inventa el dato. El trabajo termina `COMPLETADO`.
5. **Dado** que Ollama está caído, **entonces** predicción, análisis y clasificación siguen funcionando y `/salud/readiness` sigue en `UP`, con `ollama: DOWN` en `informativos` (RNF-08).
6. **Dado** una respuesta del modelo que no se puede interpretar (JSON inválido al pedir el agente, llamada a una herramienta inexistente), **entonces** se reintenta una vez esa llamada al modelo; si vuelve a fallar, se elige el agente por palabras clave o se ignora la llamada inválida, y se registra.

---

### Historia 4 — Herramientas MCP de solo lectura (Prioridad: P1)

Como agente (o cliente MCP de prueba, como MCP Inspector), quiero un servidor MCP con herramientas tipadas para leer datos del sistema, para no depender de cómo es cada API (constitución §6).

**Prueba independiente:** tests de contrato de cada herramienta contra respuestas simuladas con el formato real de cada servicio.

**Escenarios de aceptación:**

1. **Dado** el servidor MCP, **cuando** un cliente pide `tools/list`, **entonces** recibe las 11 herramientas de 2.3 con su descripción en español y el esquema JSON de sus parámetros.
2. **Dado** una herramienta llamada con parámetros válidos, **entonces** consulta el endpoint correspondiente con el token de la cuenta de servicio `servicio-ia` y devuelve un resultado JSON acotado: como máximo 50 elementos, con `total` y `truncado`.
3. **Dado** parámetros inválidos (UUID mal formado, estado inexistente), **entonces** la herramienta devuelve un error de herramienta (`isError`) con el motivo, sin llamar al servicio.
4. **Dado** un `404` del servicio (por ejemplo, `CAMPANIA_NO_ENCONTRADA`), **entonces** devuelve un error de herramienta legible con ese código.
5. **Dado** cualquier herramienta, **entonces** solo hace `GET` (el cliente de `spec-base.md` no tiene otros métodos).
6. **Dado** textos libres de los datos (observaciones de labores, descripciones de incidencias), **entonces** se recortan a 200 caracteres y se entregan como datos dentro del JSON, nunca como instrucciones (constitución §6).
7. **Dado** gerencia con un cliente MCP externo, **cuando** se conecta a `/api/ia/v1/mcp` con su token, **entonces** puede listar y llamar las herramientas; sin token, `401`; sin `gerencia`, `403`.

### Casos borde

- **El modelo responde en inglés:** el mensaje de sistema exige español; si aun así responde en otro idioma, se acepta (no se valida el idioma).
- **La pregunta trae una cifra** ("¿Qué campañas costaron más de 30000?"): la cifra de la pregunta cuenta como respaldada.
- **Dos consultas a la vez:** cada una tiene su propio estado de grafo y su propia sesión MCP; comparten el cliente HTTP y el token de servicio.
- **Herramienta con resultado enorme** (históricos con 500 campañas): se recorta a 50 elementos y se ordena por relevancia según la herramienta (por ejemplo, costo por hectárea descendente si se pide así); el agente ve `truncado: true`.
- **Datos personales:** los nombres de responsables pueden aparecer en `datos` y en la respuesta (son datos del sistema que gerencia ya puede ver), pero no en los logs.

## 1.3 Requisitos

### Requisitos funcionales

- **RQ-AGE-01:** `POST /consultas-agente` valida la pregunta y crea un trabajo `CONSULTA_AGENTE` con tiempo límite de 120 s.
- **RQ-AGE-02:** el grafo de LangGraph clasifica la pregunta (`campanias`, `inventario`, `fuera_de_alcance`), ejecuta el agente elegido con sus herramientas, redacta y verifica las cifras.
- **RQ-AGE-03:** los agentes usan las herramientas a través de una sesión de cliente MCP contra el servidor MCP del propio servicio, no llamando funciones directamente.
- **RQ-AGE-04:** límites: 6 llamadas a herramientas, 12 pasos del grafo, 60 s por llamada al modelo y 120 s por consulta.
- **RQ-AGE-05:** verificación de cifras según la Historia 2.
- **RQ-AGE-06:** el servidor MCP expone las 11 herramientas de 2.3, todas de solo lectura y con resultados acotados.
- **RQ-AGE-07:** el servidor MCP también se publica por HTTP en `/api/ia/v1/mcp` para `gerencia` (demostración e inspección con clientes MCP estándar).
- **RQ-AGE-08:** Ollama como comprobación informativa de salud, con un estado en caché de 30 s que también usa `POST /consultas-agente` para fallar rápido.
- **RQ-AGE-09:** cada consulta registra en su trabajo la pregunta, el agente, las herramientas con sus tiempos, el resultado y el `idCorrelacion`; los logs registran el agente, las herramientas, los tiempos y el estado, sin la pregunta ni los datos.

### Entidades clave

No hay colecciones nuevas: la consulta y su resultado viven en el trabajo (`spec-trabajos.md`).

`EstadoAgente` (estado del grafo, en memoria): `pregunta`, `agente`, `mensajes`, `llamadas` (herramienta, argumentos, resultado, duración, error), `pasos`, `respuesta`, `cifrasOmitidas`.

## 1.4 Permisos

| Operación | Roles |
|---|---|
| `POST /consultas-agente` | `gerencia` |
| `/api/ia/v1/mcp` | `gerencia` |
| Consultar el trabajo | Su solicitante |
| Llamadas de las herramientas a los microservicios | Cuenta de servicio `servicio-ia` (`lectura_gestion`, `lectura_inventario`, `lectura_operaciones`) |

## 1.5 Errores de esta funcionalidad

| HTTP | Código | Mensaje | Cuándo |
|---|---|---|---|
| 400 | `DATOS_INVALIDOS` | (común) | Pregunta vacía o de más de 1.000 caracteres |
| 503 | `MODELO_LENGUAJE_NO_DISPONIBLE` | "El asistente no está disponible en este momento. Intente más tarde." | Ollama caído según la última comprobación |
| 503 | `DEPENDENCIA_NO_DISPONIBLE` | (común) | Firestore o RabbitMQ al crear el trabajo |

Códigos del `error` de un trabajo `CONSULTA_AGENTE` `FALLIDO`: `MODELO_LENGUAJE_NO_DISPONIBLE`, `LIMITE_PASOS_AGENTE` ("La consulta necesitó más pasos de los permitidos. Intente una pregunta más concreta.") y los comunes de `spec-trabajos.md`.

## 1.6 Criterios de éxito

- **CE-AGE-01:** los escenarios de las historias 1 a 4 pasan como tests automáticos, sin Ollama.
- **CE-AGE-02:** con Ollama y `qwen2.5:3b` en local, las 10 preguntas de `tests/fixtures/preguntas_agente.json` (5 de campañas, 4 de inventario, 1 fuera de alcance) eligen el agente esperado y llaman al menos una herramienta pertinente en 8 o más casos (prueba manual, ver T09).
- **CE-AGE-03:** con esas mismas preguntas, ninguna respuesta final contiene una cifra que no esté en `datos` (la verificación lo garantiza; la prueba lo confirma de punta a punta).
- **CE-AGE-04:** una consulta típica (1 o 2 herramientas) termina en menos de 60 s en el equipo de desarrollo.
- **CE-AGE-05:** `docs/agentes.md` describe los agentes, el grafo, las herramientas MCP con sus parámetros, la verificación de cifras, los límites y la configuración de Ollama (§1.7.6 del documento de requisitos).
- **CE-AGE-06:** cobertura ≥ 80 % en `agentes` y `mcp_server` (constitución §8), Ruff y mypy sin errores, pipeline en verde.

## 1.7 Supuestos

- Ollama corre nativo en Windows y el contenedor lo alcanza en `http://host.docker.internal:11434` (ya en `docker-compose.yml`); en la nube, en Compute Engine. El modelo es `OLLAMA_MODEL` (`qwen2.5:3b`), que admite llamadas a herramientas.
- La cuenta de servicio `servicio-ia` ya tiene los tres roles de lectura y las tres audiencias en el realm.
- `lectura_inventario` no permite leer movimientos (`servicio-inventario/specs/spec-movimientos.md`, AC-01). El consumo de insumos se obtiene de las labores (sus `insumos`).

## 1.8 Aclaraciones

- **AC-01 — ¿Por qué los agentes pasan por MCP si el servidor está en el mismo proceso?** Es lo que pide el documento de requisitos (RF-23: "consulten los microservicios mediante herramientas MCP") y mantiene un solo contrato para las herramientas: el agente las descubre con `tools/list` y las llama con `tools/call`, igual que lo haría un cliente externo. Dentro del proceso se usa el transporte en memoria del SDK (sin red); hacia afuera, HTTP en `/api/ia/v1/mcp`.
- **AC-02 — ¿Por qué un grafo con clasificación y no un solo agente con todas las herramientas?** Con un modelo pequeño (3B), 11 herramientas a la vez confunden más que 5 o 6. Además, el documento pide agentes separados (monitoreo de campañas, inventario, reportes).
- **AC-03 — ¿Por qué se quitan oraciones en vez de corregir la cifra?** Corregirla exigiría saber qué quiso decir el modelo. Quitarla es la regla de la constitución §6 ("si no se puede verificar, se omite") y no puede introducir un error nuevo.
- **AC-04 — ¿Por qué no hay conversación con historial?** CU-17 es una consulta puntual. Con historial, el contexto crece y un modelo de 3B pierde precisión. Cada consulta es independiente.
- **AC-05 — ¿Por qué el agente no tiene herramientas del propio servicio (predicción, análisis)?** Guardan resultados y la regla de dependencias no permite que `mcp_server` use `prediccion`. Gerencia ya tiene esos endpoints directos. Se puede agregar en una spec futura con una enmienda.

## 1.9 Fuera de alcance

- Conversación con historial y memoria entre consultas.
- Herramientas de escritura (RN-14).
- Respuestas en streaming (el resultado se consulta por polling, RF-24).
- El agente de reportes (`spec-reportes.md`).
- Proveedores de modelos de lenguaje externos (constitución §1).

---

# 2. Plan

Criterio general: lo mínimo que cumple la spec y la constitución. Reutiliza `ClienteGateway` y `trabajos`.

**Documentos que debe tener a mano quien implemente:** la constitución, `specs/README.md`, `spec-base.md`, `spec-trabajos.md`, este archivo y las specs de lectura de los tres servicios (2.3).

## 2.1 Dependencias

| Dependencia | Para qué |
|---|---|
| `mcp` (MCP Python SDK) | Servidor `FastMCP`, cliente `ClientSession` y transportes en memoria y HTTP (constitución §2) |

*Implementado (2026-11-05):* `mcp` 2.3, `langgraph` 1.2 y `ollama` 0.6. En `mcp` 2.x, `FastMCP` se llama `MCPServer` (`mcp.server.mcpserver`) y el cliente es `mcp.Client`: con un `MCPServer` se conecta en el mismo proceso y con `streamable_http_client` por HTTP. Al cerrar el `Client`, una excepción que salga de su bloque llega envuelta en un `ExceptionGroup` (usa un grupo de tareas), así que el manejador la captura dentro del bloque.
| `langgraph` | Grafo de estado de los agentes (constitución §2) |
| `ollama` | Cliente oficial de Ollama: chat con herramientas y salida con esquema JSON |

No se usa LangChain: los nodos llaman al `Protocol ModeloLenguaje` directamente, así el modelo se reemplaza en los tests sin librerías extra.

## 2.2 Configuración

| Variable | Obligatoria | Uso | Valor local |
|---|---|---|---|
| `OLLAMA_BASE_URL` | Sí | URL de Ollama | Ya en Docker Compose |
| `OLLAMA_MODEL` | Sí | Modelo | Ya en Docker Compose (`qwen2.5:3b`) |
| `AGENTES_NUM_CTX` | No (8192) | Contexto del modelo | — |

Temperatura 0 en todas las llamadas (respuestas reproducibles dentro de lo posible).

## 2.3 Herramientas MCP (`mcp_server/`)

Todas reciben y devuelven JSON; los decimales siguen como texto (README D-03); los listados devuelven `{ items, total, truncado }` con 50 elementos como máximo.

| Herramienta | Parámetros | Endpoint | Recorte |
|---|---|---|---|
| `listar_parcelas` | `nombre?` | `GET /api/gestion/v1/parcelas` | 50 |
| `listar_cultivos` | — | `GET /api/gestion/v1/cultivos` | 50 |
| `listar_campanias` | `estado?`, `idParcela?`, `idCultivo?` | `GET /api/gestion/v1/campanias` | 50, más recientes primero |
| `obtener_campania` | `idCampania` | `GET /api/gestion/v1/campanias/{id}` (con `resumen`) | — |
| `obtener_costos_campania` | `idCampania` | `GET /api/gestion/v1/campanias/{id}/costos?tamanio=50` (con `costoTotal` y `subtotalesPorCategoria`) | 50 |
| `obtener_indicadores_campania` | `idCampania` | `GET /api/gestion/v1/campanias/{id}/indicadores` | — |
| `listar_historicos` | `idCultivo?`, `fechaFinalizacionDesde?`, `fechaFinalizacionHasta?`, `ordenarPor?` (`costoPorHectarea`, `rendimientoPorHectarea`, `fechaFinalizacion`) | `GET /api/gestion/v1/campanias/historicos?tamanio=500` | 50, según `ordenarPor` descendente |
| `consultar_estado_inventario` | `categoria?`, `soloStockBajo?` | `GET /api/inventario/v1/estado-inventario` | 50 |
| `obtener_insumo` | `idInsumo` | `GET /api/inventario/v1/insumos/{id}` | — |
| `listar_labores` | `idCampania?`, `estado?`, `fechaDesde?`, `fechaHasta?` | `GET /api/operaciones/v1/labores?limite=50` | 50 (primera página del cursor) |
| `listar_incidencias` | `idParcela?`, `idCampania?`, `tipo?`, `fechaDesde?`, `fechaHasta?` | `GET /api/operaciones/v1/incidencias?limite=50` | 50 |

**Parámetro `maximo` (lo pide `spec-reportes.md` 2.3):** `listar_campanias`, `listar_historicos`, `consultar_estado_inventario`, `listar_labores` y `listar_incidencias` aceptan además `maximo` (1 a 500, por defecto 50) y paginan el servicio hasta alcanzarlo; `listar_labores` y `listar_incidencias` siguen el cursor de `servicio-operaciones`. Los agentes conversacionales (`campanias`, `inventario`) no lo ven: `agentes/herramientas.py` lo quita del esquema que reciben, para que el modelo no llene su contexto. Lo usa el agente de reportes con `maximo = 500`.

- Los parámetros se declaran con tipos de Pydantic (UUID, enumeraciones con los valores reales de cada servicio, fechas `AAAA-MM-DD`), así `FastMCP` genera el esquema y rechaza lo inválido antes de llamar al servicio.
- Los nombres exactos de filtros y campos se confirman contra el OpenAPI de cada servicio al implementar; si alguno difiere de esta tabla, se corrige aquí.
- **Verificado contra el código de cada servicio (2026-11-05):**
  - **Gestión.** Las páginas son `{ items, pagina, tamanio, total }`, con `pagina` desde 0 y `tamanio` máximo 100 (500 en históricos).
    - `listar_campanias` sale ordenado por `fechaInicio` descendente y no trae `resumen`.
    - `listar_historicos` acepta además `idParcela`. Cada histórico trae `nombreParcela`, `nombreCultivo`, `costoTotal`, `costosPorCategoria`, `rendimientoPorHectarea`, `costoPorHectarea` y `motivosNoDisponible`.
    - Valores reales: `EstadoCampania` = `PLANIFICADA`, `EN_CURSO`, `FINALIZADA`; `CategoriaCosto` = `INSUMO`, `MANO_DE_OBRA`, `MAQUINARIA`, `OTRO`.
  - **Inventario.** `estado-inventario` devuelve además `resumen` (`totalInsumos`, `totalStockBajo`), con `tamanio` máximo 100. `CategoriaInsumo` = `SEMILLA`, `FERTILIZANTE`, `FITOSANITARIO`.
  - **Operaciones.** Las páginas son `{ items, siguienteCursor }`, sin `total`, con `limite` máximo 100. Por eso `total` es la cantidad reunida y `truncado` indica que quedaban más.
    - `GET /labores` exige al menos uno de `idCampania`, `idResponsable`, `mias` o `estado`. Con la cuenta de servicio solo sirven `idCampania` y `estado`, así que `listar_labores` exige uno de los dos.
    - `GET /incidencias` exige `idParcela`, `idCampania` o `mias`, así que `listar_incidencias` exige uno de los dos primeros.
    - Una herramienta sin el filtro obligatorio devuelve un error de herramienta sin llamar al servicio.
    - `EstadoLabor` = `PROGRAMADA`, `PENDIENTE`, `CONFIRMADA`, `RECHAZADA`, `PENDIENTE_REVISION`; `tipo` de incidencia = `PLAGA`, `ENFERMEDAD`, `DANIO`, `OTRO`.
- Cada herramienta reduce la respuesta a los campos útiles para responder (por ejemplo, sin `version`, `huella` ni fechas técnicas) y recorta los textos libres a 200 caracteres.
- `ErrorServicioRemoto` → error de herramienta con un texto como "servicio-gestion no disponible" o "CAMPANIA_NO_ENCONTRADA: la campaña no existe".
- **`mcp_server/servidor.py`:** `crear_servidor_mcp(cliente_gateway) -> FastMCP` registra las herramientas. Se crea una vez en el `lifespan`.
- **Publicación HTTP:** la aplicación de *streamable HTTP* de `FastMCP` (modo sin estado) se monta en `/api/ia/v1/mcp`. Un middleware ASGI propio delante del montaje valida el JWT y el rol `gerencia` con las mismas funciones de `comun/seguridad.py` (el montaje no pasa por las dependencias del router). *Implementado* (`mcp_server/http.py`):
  - En lugar de montarse, se registra como ruta exacta, porque un `Mount` no acepta la ruta sin barra final que usan los clientes MCP.
  - El transporte es sin estado y con respuestas JSON, y su gestor de sesiones arranca en el `lifespan`.
  - Usa `host="0.0.0.0"` para desactivar la protección contra *DNS rebinding* del SDK: está pensada para servidores locales sin autenticación, y aquí las solicitudes llegan por el gateway y con JWT.
  - `validar_token` se extrajo de `usuario_actual` para que ambos validen igual.
  - El logger `mcp` queda en `WARNING`: en `INFO` registra los argumentos de las herramientas que fallan (RQ-AGE-09).

## 2.4 Modelo de lenguaje (`integracion/modelo_lenguaje.py`)

- `Protocol ModeloLenguaje`:
  - `async chat(mensajes, herramientas=None, formato=None) -> RespuestaModelo` (texto y llamadas a herramientas);
  - `async disponible() -> bool`.
- `ModeloOllama`: `ollama.AsyncClient(host=OLLAMA_BASE_URL)`, `chat(model, messages, tools, format, options={temperature: 0, num_ctx})` con tiempo límite de 60 s. Errores de conexión o `ResponseError` → `ModeloLenguajeNoDisponible`. `disponible()` consulta `GET /api/tags` y verifica que esté `OLLAMA_MODEL`; el resultado se guarda 30 s.
- `ModeloGuion` (en `tests/`): devuelve respuestas fijas en orden y registra los mensajes y herramientas que recibió, para que los tests verifiquen qué se le pidió.

## 2.5 Grafo (`agentes/`)

```text
agentes/
├── estado.py        # EstadoAgente (TypedDict) y límites
├── grafo.py         # construir_grafo(modelo, sesion_mcp) -> StateGraph compilado
├── nodos.py         # clasificar, actuar, ejecutar_herramientas, redactar, verificar, fuera_de_alcance
├── cifras.py        # verificación de cifras: funciones puras
├── herramientas.py  # qué herramientas ve cada agente; conversión MCP → formato de herramientas de Ollama
├── prompts/         # mensajes de sistema en archivos .md, uno por nodo y agente
└── servicio.py      # manejador del trabajo CONSULTA_AGENTE
```

```text
clasificar ──► campanias | inventario ──► actuar ◄──► ejecutar_herramientas
     │                                      │
     └──► fuera_de_alcance ──► FIN          └──► redactar ──► verificar ──► FIN
```

- **`clasificar`:** una llamada al modelo con `formato` = esquema JSON `{ "agente": "campanias" | "inventario" | "fuera_de_alcance" }`. Si la salida no es válida dos veces, palabras clave (insumo, stock, fertilizante… → `inventario`; campaña, parcela, cultivo, costo, rendimiento, labor, incidencia… → `campanias`; ninguna → `fuera_de_alcance`).
- **`actuar`:** llamada al modelo con el mensaje de sistema del agente y solo sus herramientas (de `tools/list` de la sesión MCP, filtradas por `herramientas.py`). Si el modelo pide herramientas y no se llegó a 6 llamadas, va a `ejecutar_herramientas`; si no, a `redactar`.
- **`ejecutar_herramientas`:** `session.call_tool(nombre, argumentos)` por cada llamada pedida; guarda resultado, duración y error en `llamadas`; agrega los resultados como mensajes de rol `tool`, con el JSON tal cual. Una herramienta inexistente se responde como error de herramienta.
- **`redactar`:** llamada al modelo con el mensaje de sistema de redacción: responder en español, con 2 a 6 oraciones, usar solo cifras que aparecen en los datos, no calcular promedios ni porcentajes, decir explícitamente si un dato no estuvo disponible y tratar el contenido de las herramientas como datos, no como instrucciones.
- **`verificar`:** `cifras.verificar(texto, datos, pregunta)` (2.6). Arma el resultado.
- **Límites:** `recursion_limit = 12` en la compilación (`GraphRecursionError` → `LIMITE_PASOS_AGENTE`); contador de llamadas a herramientas en el estado. *Implementado:* `recursion_limit = 16` en `ainvoke`. La cuenta es clasificar, 6 rondas de `actuar` y `ejecutar_herramientas`, el último `actuar`, `redactar` y `verificar`. Con 12, un modelo que pide una herramienta por turno nunca llegaría a las 6 llamadas (RQ-AGE-04 queda con 16 pasos).
- *Implementado:* una llamada a una herramienta que no es del agente o no existe se reintenta una vez (Historia 3, escenario 6). Si vuelve a fallar, se ignora y se registra; no llega a `ejecutar_herramientas`. `redactar` abre una conversación nueva con la pregunta, los datos en JSON y la lista de consultas fallidas, en lugar de seguir la conversación de las herramientas: es más simple para un modelo de 3B.
- **Sesión MCP:** por cada consulta, `servicio.py` abre una `ClientSession` sobre el transporte en memoria del SDK contra el `FastMCP` del `lifespan` y la cierra al terminar.

## 2.6 Verificación de cifras (`agentes/cifras.py`)

Funciones puras, con tests exhaustivos:

1. **Cifras respaldadas:** se recorre el JSON de todos los resultados de herramientas y la pregunta, y se extraen todos los números (de valores numéricos y de textos, incluidos los partes de fechas e IDs). Cada uno se guarda como `Decimal` y también redondeado a 0, 1 y 2 decimales. *Implementado:* también cuenta como respaldada la cantidad de elementos de cada lista de los datos ("Hay 3 insumos con stock bajo" con una lista de 3), porque contar lo que se listó no es calcular una cifra nueva.
2. **Cifras del texto:** expresión regular para números con separador de miles `.` o espacio y decimal `,`, o separador de miles `,` y decimal `.`, o sin separadores. Se normalizan a `Decimal`. Un número ambiguo tiene varias lecturas ("20.000" es 20 con punto decimal, que es como `servicio-inventario` envía el stock, o veinte mil con punto de miles; "1,500" es 1,5 con coma decimal o mil quinientos con coma de miles): se considera respaldado si **alguna** de sus lecturas lo está. Se ignoran los números que forman parte de palabras ("COVID19") y los ordinales escritos con letra.
3. **Oraciones:** el texto se divide en oraciones; se quita toda oración que tenga al menos una cifra no respaldada.
4. **Resultado:** texto verificado, cantidad de oraciones quitadas y, si no queda ninguna, el texto fijo de la Historia 2, escenario 3.

## 2.7 Endpoint y trabajo

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /api/ia/v1/consultas-agente` | `gerencia` | `202` + trabajo (`spec-trabajos.md`) | 400, 401, 403, 503 `MODELO_LENGUAJE_NO_DISPONIBLE` o `DEPENDENCIA_NO_DISPONIBLE` |
| `/api/ia/v1/mcp` (MCP *streamable HTTP*) | `gerencia` | Protocolo MCP | 401, 403 |

**Solicitud:** `{ "pregunta": "¿Qué insumos están bajo el mínimo?" }` (`pregunta` de 3 a 1.000 caracteres, recortada).

**Resultado del trabajo:**

```json
{
  "pregunta": "¿Qué insumos están bajo el mínimo?",
  "agente": "inventario",
  "respuesta": "Hay 2 insumos con stock bajo. Glifosato tiene 20 litros, igual a su nivel mínimo.",
  "herramientas": [
    { "nombre": "consultar_estado_inventario", "argumentos": { "soloStockBajo": true }, "duracionMs": 312, "error": null }
  ],
  "datos": [
    { "herramienta": "consultar_estado_inventario", "resultado": { "items": [ ], "total": 2, "truncado": false } }
  ],
  "cifrasOmitidas": 0,
  "modeloLenguaje": "qwen2.5:3b",
  "aviso": "Respuesta redactada por un modelo de lenguaje a partir de los datos consultados. Las cifras se verificaron contra esos datos."
}
```

El tipo `CONSULTA_AGENTE` se registra en `crear_app()` con tiempo límite de 120 s. `ModeloLenguajeNoDisponible` durante la consulta se lanza como `ErrorAplicacion` con `MODELO_LENGUAJE_NO_DISPONIBLE`, así el consumidor lo guarda como error del trabajo (`spec-trabajos.md` 2.9).

## 2.8 Salud

Comprobación **informativa** `ollama` (`spec-base.md` 2.8) con `ModeloLenguaje.disponible()`.

## 2.9 Documentación

`docs/agentes.md`: propósito de cada agente, diagrama del grafo, tabla de herramientas MCP con parámetros y endpoints, reglas de redacción y de verificación de cifras, límites, cómo conectar MCP Inspector a `/api/ia/v1/mcp` y configuración de Ollama (modelo, `num_ctx`, cómo descargarlo con `ollama pull`).

## 2.10 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `tests/unit/agentes/test_cifras.py` | Historia 2 completa: formatos de número, fechas e IDs, cifras de la pregunta, redondeos, oraciones quitadas, todo quitado |
| Unitario | `tests/unit/agentes/test_grafo.py` | Con `ModeloGuion` y un servidor MCP con herramientas simuladas: clasificación y su respaldo por palabras clave, herramientas que ve cada agente, tope de 6 llamadas, `LIMITE_PASOS_AGENTE`, herramienta inexistente, error de herramienta que se informa en la respuesta, fuera de alcance sin herramientas (Historias 1 y 3) |
| Unitario | `tests/unit/agentes/test_servicio.py` | Manejador: resultado del trabajo, `MODELO_LENGUAJE_NO_DISPONIBLE`, registro sin la pregunta en los logs |
| Contrato | `tests/unit/mcp_server/test_herramientas_*.py` | Cada herramienta contra respuestas simuladas (`httpx.MockTransport`) copiadas de los ejemplos de las specs de cada servicio: endpoint y parámetros pedidos, recorte a 50, `truncado`, orden de `listar_historicos`, recorte de textos, parámetros inválidos sin llamada, `404` y servicio caído como error de herramienta (Historia 4) |
| Unitario | `tests/unit/mcp_server/test_lista_herramientas.py` | `tools/list` con las 11 herramientas, descripciones y esquemas |
| Integración | `tests/integration/agentes/test_router_agentes.py` | `POST /consultas-agente` con validación, permisos, fallo rápido con Ollama caído, flujo completo con RabbitMQ y `ModeloGuion`; `/api/ia/v1/mcp` con un cliente MCP del SDK (con token, sin token, sin rol) |

Los ejemplos de respuesta de los otros servicios se guardan en `tests/fixtures/servicios/` con una nota de su origen (archivo de spec).

---

# 3. Tareas

Cada tarea se da por terminada solo con sus tests en verde. Las marcadas con **[P]** pueden hacerse en paralelo con la anterior.

- [x] **T01** — Agregar las dependencias y variables de 2.1 y 2.2. Revisar el OpenAPI real de los tres servicios y ajustar la tabla de 2.3 si algún filtro o campo difiere. Guardar los ejemplos en `tests/fixtures/servicios/`. Hecho (2026-11-05): `mcp` 2.3, `langgraph` 1.2 y `ollama` 0.6. La tabla de 2.3 se verificó contra el código de los tres servicios. Diferencias: `listar_historicos` acepta `idParcela`, las labores y las incidencias exigen filtro, y operaciones no devuelve `total`. Hay 10 ejemplos en `tests/fixtures/servicios/`.
- [x] **T02** — Implementar las 11 herramientas y `crear_servidor_mcp`. *Hecho cuando:* pasan los tests de contrato y `test_lista_herramientas.py`. Hecho: 27 tests de contrato y `test_lista_herramientas.py`. Los valores fijos se aceptan en minúscula.
- [x] **T03** [P] — Implementar `agentes/cifras.py`. *Hecho cuando:* pasa `test_cifras.py`. Hecho: 22 tests en `test_cifras.py`. También cuenta como respaldado el largo de las listas (2.6).
- [x] **T04** — Implementar `ModeloLenguaje`, `ModeloOllama`, `ModeloGuion` y la comprobación de salud `ollama`. Hecho. `ModeloGuion` está en `tests/modelo_guion.py`. `keep_alive` de 30 minutos, porque la carga en frío tarda unos 30 s.
- [x] **T05** — Implementar el grafo, los nodos y los mensajes de sistema. *Hecho cuando:* pasa `test_grafo.py`. Hecho: 16 tests en `test_grafo.py`. Límite de 16 pasos (2.5).
- [x] **T06** — Implementar el manejador `CONSULTA_AGENTE` y `POST /consultas-agente`. *Hecho cuando:* pasan `test_servicio.py` y la parte de consultas de `test_router_agentes.py`. Hecho: `test_servicio.py` y la parte de consultas de `test_router_agentes.py`, con flujo completo por RabbitMQ.
- [x] **T07** — Montar `/api/ia/v1/mcp` con su middleware de seguridad. *Hecho cuando:* pasa la parte MCP de `test_router_agentes.py`. Hecho: ruta exacta con `EndpointMcp` (2.3). Un cliente MCP del SDK pasa por HTTP; sin token responde `401` y sin rol, `403`.
- [x] **T08** [P] — Escribir `tests/fixtures/preguntas_agente.json` y `docs/agentes.md`. *Hecho cuando:* se cumple CE-AGE-05. Hecho: `docs/agentes.md` (CE-AGE-05) y `tests/fixtures/preguntas_agente.json`.
- [x] **T09** — Prueba manual con Ollama y los servicios del perfil `backend` con datos de prueba: las 10 preguntas a través del gateway con `gerencia.prueba`, y MCP Inspector conectado a `/api/ia/v1/mcp`. *Hecho cuando:* se cumplen CE-AGE-02 a CE-AGE-04; se anota el resultado de cada pregunta en esta tarea. Hecho (2026-11-05), con Ollama en Windows (GPU), `qwen2.5:3b` y datos de demostración cargados por la API. Las 10 preguntas pasaron por el gateway con `gerencia.prueba`; el detalle de cada una está en `docs/agentes.md`. Resultados: 10 de 10 eligieron el agente y una herramienta pertinente (CE-AGE-02), ninguna cifra quedó sin respaldo (CE-AGE-03) y la más lenta tardó 37,1 s (CE-AGE-04). La primera pasada dio 8/10 y se ajustaron los mensajes de sistema, los errores de parámetros y las mayúsculas. El MCP se probó con el cliente del SDK a través del gateway (`http://localhost:8080/api/ia/v1/mcp`): 11 herramientas, llamadas con datos reales, `401` y `403`. MCP Inspector no se abrió, porque necesita interfaz gráfica; los pasos para usarlo están en `docs/agentes.md`.
