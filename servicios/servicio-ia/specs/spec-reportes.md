# Reportes por texto o voz y reportes programados — `servicio-ia`

| Campo | Valor |
|---|---|
| Servicio | `servicio-ia` |
| Archivo | `specs/spec-reportes.md` |
| Estado | Spec en borrador · Plan y tareas en borrador |
| Fecha | 2026-11-04 |
| Constitución | v4.0.0 (secciones 1, 2, 4, 6, 7, 9 y 10) |
| Trazabilidad | CU-18, CU-25 · RF-24, RF-25, RF-34 · RN-14 · proceso 8 y 11 del documento de requisitos · Módulo 8 (n8n) |
| Depende de | `spec-trabajos.md` (tipo `REPORTE`), `spec-prediccion.md` (`AlmacenArchivos`), `spec-agentes.md` (herramientas MCP, `ModeloLenguaje`, verificación de cifras) |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## 1.1 Contexto

Gerencia pide un reporte escribiendo o hablando ("Quiero el reporte de costos de la campaña Soya verano 2026 en Excel") y lo descarga en PDF, Excel o CSV (CU-18, proceso 8). n8n pide reportes periódicos y los envía por correo (CU-25, RF-34, proceso 11).

El documento de requisitos exige que el reporte use "exclusivamente cálculos de los microservicios; el modelo de lenguaje interpreta y redacta, no genera cifras" (RN-14). Por eso el reporte se arma así:

| Paso | Quién | Modelo de lenguaje |
|---|---|---|
| 1. Transcribir el audio | Faster-Whisper | — |
| 2. Interpretar la solicitud en un tipo de reporte con filtros | Agente de reportes | Sí, con salida en esquema JSON. n8n y los formularios envían la solicitud ya estructurada y se saltan este paso |
| 3. Obtener los datos | Herramientas MCP de `spec-agentes.md`, llamadas por el agente según el tipo de reporte (fijo, no las elige el modelo) | No |
| 4. Armar las tablas | Código, con los datos tal cual | No |
| 5. Redactar un resumen de 2 a 5 oraciones | Agente de reportes | Sí; cifras verificadas con `spec-agentes.md` 2.6 |
| 6. Generar los archivos | WeasyPrint (PDF), OpenPyXL (Excel) y `csv` (CSV) | No |

### Catálogo de reportes

| Tipo | Contenido | Filtros | Herramientas |
|---|---|---|---|
| `CAMPANIAS_FINALIZADAS` | Una fila por campaña finalizada: parcela, cultivo, superficie, fechas, producción, costo total, costo por categoría, rendimiento y costo por hectárea | `idCultivo?`, `fechaFinalizacionDesde?`, `fechaFinalizacionHasta?` | `listar_historicos` |
| `COSTOS_CAMPANIA` | Datos de la campaña, subtotales por categoría y lista de costos | `idCampania` (obligatorio) | `obtener_campania`, `obtener_costos_campania`, `obtener_indicadores_campania` |
| `INVENTARIO` | Una fila por insumo: categoría, unidad, stock, nivel mínimo, stock bajo y última alerta | `categoria?`, `soloStockBajo?` | `consultar_estado_inventario` |
| `LABORES` | Una fila por labor: tipo, parcela, campaña, estado, fechas, responsable e insumos | `fechaDesde`, `fechaHasta` (por defecto, los últimos 30 días), `estado?`, `idCampania?` | `listar_labores` |
| `INCIDENCIAS` | Una fila por incidencia: tipo, parcela, campaña, fecha, descripción y clasificación de IA | `fechaDesde`, `fechaHasta` (por defecto, los últimos 30 días), `tipo?`, `idParcela?` | `listar_incidencias` |

Las cifras de las tablas son las que devuelven los servicios. Este servicio no suma, no promedia ni calcula porcentajes (RN-14); solo cuenta filas.

### Formatos

| Formato | Contenido |
|---|---|
| `PDF` | Título, fecha de generación, filtros, resumen, tablas, aviso y fuentes de los datos |
| `XLSX` | Hoja `Resumen` (título, filtros, resumen, aviso) y una hoja por tabla, con números como números |
| `CSV` | La tabla principal del reporte, UTF-8 con BOM (para que Excel lea bien las tildes), separador coma y punto decimal |

## 1.2 Escenarios de usuario y pruebas

### Historia 1 — Pedir un reporte por texto (Prioridad: P1)

Como gerencia, quiero escribir qué reporte necesito y en qué formato, y descargarlo cuando esté listo (CU-18).

**Por qué esta prioridad:** es el flujo principal; la voz y los programados lo reutilizan.

**Prueba independiente:** con el modelo de lenguaje simulado (`ModeloGuion`) y los servicios simulados.

**Escenarios de aceptación:**

1. **Dado** el texto "Reporte de insumos con stock bajo en PDF y Excel", **cuando** gerencia lo envía a `POST /reportes`, **entonces** recibe `202` con el trabajo; al terminar, el `resultado` trae:
   - la solicitud interpretada (`tipo = INVENTARIO`, `filtros = { soloStockBajo: true }`, `formatos = [PDF, XLSX]`);
   - el título, el resumen verificado y `cifrasOmitidas`;
   - una vista previa de la tabla principal (hasta 50 filas) para mostrarla en React;
   - los archivos, cada uno con formato, nombre, tamaño, SHA-256 y su ruta de descarga.
2. **Dado** una solicitud que nombra una campaña ("costos de la campaña Soya verano 2026"), **entonces** se busca por nombre con `listar_campanias`; con una sola coincidencia se usa su ID.
3. **Dado** que el nombre coincide con varias campañas o con ninguna, **entonces** el trabajo termina `FALLIDO` con `CAMPANIA_NO_IDENTIFICADA` y un mensaje con hasta 5 nombres parecidos.
4. **Dado** una solicitud que no corresponde a ningún tipo del catálogo, **entonces** `FALLIDO` con `REPORTE_NO_SOPORTADO` y los tipos disponibles en el mensaje.
5. **Dado** una solicitud sin formato, **entonces** se genera en PDF.
6. **Dado** un reporte sin filas (por ejemplo, ningún insumo con stock bajo), **entonces** se genera igual, con la tabla vacía y el resumen "No se encontraron registros para los filtros indicados."
7. **Dado** un usuario sin `gerencia` ni el rol de reportes programados, **entonces** `403 SIN_PERMISO`.

---

### Historia 2 — Pedir un reporte por voz (Prioridad: P1)

Como gerencia, quiero grabar mi solicitud desde React y recibir el reporte, sin escribir (proceso 8).

**Prueba independiente:** con un transcriptor simulado (devuelve un texto fijo) y, en integración, con `tests/fixtures/audio_es.webm`.

**Escenarios de aceptación:**

1. **Dado** un audio WebM (Opus), OGG, WAV o MP3 de hasta 2 minutos y 10 MB, **cuando** gerencia lo envía a `POST /reportes/voz` (con los formatos opcionales), **entonces** recibe `202` con el trabajo, y su `resultado` incluye además la `transcripcion`.
2. **Dado** el audio transcrito, **entonces** se borra del almacenamiento temporal; solo queda la transcripción (constitución §4).
3. **Dado** un audio sin voz reconocible (transcripción vacía), **entonces** `FALLIDO` con `AUDIO_SIN_VOZ`.
4. **Dado** un archivo que no es audio o que dura más de 2 minutos, **entonces** `400 AUDIO_INVALIDO` sin crear el trabajo; más de 10 MB, `400 ARCHIVO_DEMASIADO_GRANDE`.
5. **Dado** que solo `gerencia` pide reportes por voz, **entonces** la cuenta de n8n recibe `403 SIN_PERMISO` en esta ruta.

---

### Historia 3 — Pedir un reporte estructurado y recibirlo por correo (Prioridad: P1)

Como n8n, quiero pedir un reporte con su tipo y filtros exactos, enterarme cuando esté listo y descargarlo para enviarlo por correo (CU-25, RF-34).

**Prueba independiente:** con la cuenta de servicio de n8n simulada (token con su rol) y RabbitMQ.

**Escenarios de aceptación:**

1. **Dado** `{ "tipo": "INVENTARIO", "filtros": { "soloStockBajo": true }, "formatos": ["PDF"] }`, **cuando** n8n lo envía a `POST /reportes`, **entonces** recibe `202` y no se usa el modelo de lenguaje para interpretar.
2. **Dado** el reporte terminado, **entonces** se publica en el exchange `eventos` el evento `ReporteCompletado` con routing key `ia.reporte.completado`, el `idCorrelacion` de la solicitud, `origen = PROGRAMADO` y las rutas de descarga (constitución §7).
3. **Dado** el evento, **cuando** n8n descarga el archivo con su token, **entonces** lo recibe (es el solicitante del trabajo).
4. **Dado** una solicitud estructurada con Ollama caído, **entonces** el reporte se genera sin resumen (`resumen = null`, con la advertencia `RESUMEN_NO_DISPONIBLE`): los datos no dependen del modelo de lenguaje (RNF-08).
5. **Dado** una solicitud estructurada con filtros inválidos (tipo inexistente, `COSTOS_CAMPANIA` sin `idCampania`, fechas invertidas), **entonces** `400 DATOS_INVALIDOS` sin crear el trabajo.
6. **Dado** un reporte de gerencia, **entonces** el evento también se publica, con `origen = SOLICITADO`; n8n decide qué hacer con cada origen.

---

### Historia 4 — Descargar los archivos de un reporte (Prioridad: P1)

Como solicitante, quiero descargar cada archivo del reporte mientras esté disponible.

**Escenarios de aceptación:**

1. **Dado** un reporte terminado, **cuando** su solicitante pide `GET /reportes/{idTrabajo}/archivos/{formato}`, **entonces** recibe el archivo con su `Content-Type`, `Content-Disposition: attachment` con el nombre del archivo y `ETag`.
2. **Dado** otro usuario, un trabajo inexistente o un formato no generado, **entonces** `404 REPORTE_NO_ENCONTRADO`.
3. **Dado** un reporte de más de 7 días, **entonces** `404 REPORTE_EXPIRADO` (los archivos se borran a los 7 días; el trabajo dura 30).
4. **Dado** un trabajo que todavía no terminó, **entonces** `409 REPORTE_EN_PROCESO`.

---

### Historia 5 — Ninguna cifra inventada en el reporte (Prioridad: P1)

Como gerencia, quiero que las tablas sean los datos del sistema sin cambios y que el resumen no diga cifras que no estén en ellas (RN-14).

**Escenarios de aceptación:**

1. **Dado** los datos de una herramienta, **entonces** cada celda de la tabla tiene exactamente el valor recibido (en el PDF y el CSV como texto decimal; en Excel como número con el mismo valor).
2. **Dado** un resumen con una cifra que no está en las tablas, **entonces** esa oración se quita (`spec-agentes.md` 2.6).
3. **Dado** cualquier reporte, **entonces** el PDF y la hoja `Resumen` dicen qué partes redactó el modelo de lenguaje, que las cifras se verificaron y de qué servicios salieron los datos.

### Casos borde

- **Muchas filas:** cada tabla tiene como máximo 500 filas; si los datos traen más, el reporte lo indica ("Se muestran 500 de 734 registros") con el total que devolvió el servicio.
- **Textos con caracteres especiales** (comillas, saltos de línea, `=` al inicio): en CSV se escapan según RFC 4180; en CSV y Excel, un texto que empieza con `=`, `+`, `-` o `@` se antepone con `'` para que no se interprete como fórmula.
- **Nombres de archivo:** `reporte-<tipo en minúsculas>-<AAAA-MM-DD>.<ext>`, sin tildes ni espacios.
- **Whisper no está cargado aún** (primer arranque, descargando el modelo): el trabajo de voz espera hasta su tiempo límite y, si no está, `FALLIDO` con `TRANSCRIPTOR_NO_DISPONIBLE`.
- **El evento no se puede publicar** (RabbitMQ caído al terminar): se reintenta 3 veces; si falla, en un reporte `PROGRAMADO` el trabajo termina `FALLIDO` con `EVENTO_NO_PUBLICADO` (n8n no se enteraría y el correo no saldría); en uno `SOLICITADO`, se registra el error y el trabajo termina `COMPLETADO`.

## 1.3 Requisitos

### Requisitos funcionales

- **RQ-REP-01:** `POST /reportes` acepta texto libre o una solicitud estructurada (`tipo`, `filtros`, `formatos`) y crea un trabajo `REPORTE` con tiempo límite de 5 minutos.
- **RQ-REP-02:** `POST /reportes/voz` acepta un audio, lo guarda de forma temporal y crea un trabajo `REPORTE` que lo transcribe primero con Faster-Whisper.
- **RQ-REP-03:** el agente de reportes (nodo del grafo de LangGraph) interpreta el texto en una solicitud del catálogo con salida en esquema JSON, y resuelve nombres de campaña a IDs con las herramientas.
- **RQ-REP-04:** los datos se obtienen con las herramientas MCP de cada tipo, a través de una sesión de cliente MCP (como en `spec-agentes.md`), con hasta 500 elementos.
- **RQ-REP-05:** las tablas usan los datos tal cual; el resumen se verifica con la verificación de cifras de `spec-agentes.md`.
- **RQ-REP-06:** se generan los formatos pedidos (`PDF`, `XLSX`, `CSV`) y se guardan en Cloud Storage.
- **RQ-REP-07:** al terminar se publica `ReporteCompletado` (`ia.reporte.completado`) con `origen`.
- **RQ-REP-08:** `GET /reportes/{idTrabajo}/archivos/{formato}` entrega los archivos al solicitante durante 7 días.
- **RQ-REP-09:** la cuenta de servicio de n8n tiene un rol propio, `reportes_ia`, que solo permite `POST /reportes` y descargar sus archivos.

### Entidades clave

- **`SolicitudReporte`** (esquema): `tipo` (`TipoReporte`), `filtros` (según el tipo), `formatos` (lista de `FormatoReporte`: `PDF`, `XLSX`, `CSV`), `titulo?`.
- **`Reporte`** (resultado del trabajo `REPORTE`): `origen` (`SOLICITADO`, `PROGRAMADO`), `transcripcion?`, `textoSolicitud?`, `solicitud`, `titulo`, `resumen`, `cifrasOmitidas`, `advertencias`, `tablas` (vista previa), `archivos`, `fechaGeneracion`, `fechaExpiracionArchivos`, `modeloLenguaje`.

No hay colecciones nuevas: el reporte vive en el trabajo; los archivos, en Cloud Storage.

## 1.4 Permisos

| Operación | Roles |
|---|---|
| `POST /reportes` (texto o estructurado) | `gerencia`, `reportes_ia` (cuenta de servicio de n8n) |
| `POST /reportes/voz` | `gerencia` |
| `GET /reportes/{idTrabajo}/archivos/{formato}` | Su solicitante |
| Consultar el trabajo | Su solicitante (`spec-trabajos.md`) |

`reportes_ia` es un rol de realm nuevo, asignado solo al client `n8n` (2.10).

## 1.5 Errores de esta funcionalidad

| HTTP | Código | Mensaje | Cuándo |
|---|---|---|---|
| 400 | `DATOS_INVALIDOS` | (común) | Texto vacío o de más de 1.000 caracteres; solicitud estructurada inválida; formato inexistente |
| 400 | `AUDIO_INVALIDO` | "El audio no es válido o dura más de 2 minutos." | Historia 2, escenario 4 |
| 400 | `ARCHIVO_DEMASIADO_GRANDE` | (de `spec-vision.md`) | Audio de más de 10 MB |
| 404 | `REPORTE_NO_ENCONTRADO` | "El reporte solicitado no existe." | Historia 4, escenario 2 |
| 404 | `REPORTE_EXPIRADO` | "El reporte ya no está disponible. Genérelo nuevamente." | Historia 4, escenario 3 |
| 409 | `REPORTE_EN_PROCESO` | "El reporte todavía se está generando." | Historia 4, escenario 4 |
| 503 | `MODELO_LENGUAJE_NO_DISPONIBLE` | (de `spec-agentes.md`) | Texto o voz con Ollama caído según la última comprobación |
| 503 | `DEPENDENCIA_NO_DISPONIBLE` | (común) | Firestore, RabbitMQ o Cloud Storage |

Códigos del `error` de un trabajo `REPORTE` `FALLIDO`:

| Código | Mensaje |
|---|---|
| `REPORTE_NO_SOPORTADO` | "No se reconoce el reporte solicitado. Reportes disponibles: …" |
| `CAMPANIA_NO_IDENTIFICADA` | "No se pudo identificar la campaña. Campañas parecidas: …" |
| `AUDIO_SIN_VOZ` | "No se reconoció voz en el audio." |
| `TRANSCRIPTOR_NO_DISPONIBLE` | "La transcripción de voz no está disponible en este momento." |
| `EVENTO_NO_PUBLICADO` | "El reporte se generó pero no se pudo notificar. Intente nuevamente." |
| `MODELO_LENGUAJE_NO_DISPONIBLE`, `DEPENDENCIA_NO_DISPONIBLE` y los comunes de `spec-trabajos.md` | — |

## 1.6 Criterios de éxito

- **CE-REP-01:** los escenarios de las historias 1 a 5 pasan como tests automáticos, sin Ollama ni Whisper reales.
- **CE-REP-02:** un reporte estructurado de inventario en los tres formatos se genera en menos de 15 s; un reporte por voz de 15 s de audio, en menos de 90 s en el equipo de desarrollo (Whisper `small` en CPU).
- **CE-REP-03:** el PDF se abre en un lector estándar con tildes y ñ correctas; el XLSX se abre en Excel y LibreOffice con números en las celdas numéricas; el CSV se abre en Excel con tildes correctas.
- **CE-REP-04:** con Ollama y Whisper reales, las solicitudes de `tests/fixtures/solicitudes_reporte.json` (una por tipo, 2 de ellas como audio grabado) se interpretan en el tipo y los filtros esperados en 5 de 7 casos o más (prueba manual, ver T10).
- **CE-REP-05:** cobertura ≥ 80 % (README D-13), Ruff y mypy sin errores, pipeline en verde.

## 1.7 Supuestos

- React graba con la MediaRecorder API del navegador, que en Chrome y Edge produce WebM con Opus. El documento de requisitos menciona `.wav` y `.mp3`; se aceptan los cuatro.
- Faster-Whisper descarga su modelo (`WHISPER_MODEL`, `small`) la primera vez y lo guarda en `/cache` (volumen `ia-cache` de Docker Compose). En Cloud Run, el modelo se incluye en la imagen al construirla, para no descargarlo en cada instancia.
- El flujo de n8n (programación, destinatarios y envío del correo) lo define la spec de n8n. Esta spec fija lo que n8n necesita de este servicio: la solicitud estructurada, el evento y la descarga.
- El realm agrega el rol `reportes_ia` y lo asigna al client `n8n`, cuya audiencia `servicio-ia` ya existe.

## 1.8 Aclaraciones

- **AC-01 — ¿Por qué un catálogo fijo de reportes y no reportes libres?** Con un catálogo, cada tabla se arma con código a partir de datos del servicio (RN-14) y se puede probar. Un reporte libre obligaría al modelo a decidir columnas y cálculos, que es justo lo que RN-14 prohíbe. El modelo solo decide **qué** reporte y con **qué** filtros.
- **AC-02 — ¿Por qué los archivos se descargan a través de la API y no con URL firmadas?** Resuelta con la constitución v4.0.0 §4. Una URL firmada del emulador de Cloud Storage tiene que resolver a la vez desde el navegador (`localhost`) y desde n8n (red de Docker), y en GCP exige permisos de firma para la cuenta del servicio. A través de la API, React y n8n descargan con el token que ya tienen, solo el solicitante accede y no hace falta CORS en el bucket. Es el mismo criterio que la descarga de modelos (`spec-vision.md` AC-02).
- **AC-03 — ¿Por qué CSV solo trae la tabla principal?** Un CSV es una sola tabla. El reporte de costos tiene dos (subtotales y lista); el CSV trae la lista, y los subtotales quedan en PDF y Excel.
- **AC-04 — ¿Por qué no hay gráficos?** Ningún requisito los pide en los reportes y React ya grafica con Recharts. Se puede agregar en otra spec.
- **AC-05 — ¿Por qué el evento se publica también para los reportes de gerencia?** La constitución §7 pide publicarlo "al terminar un reporte". Con `origen` en el evento, n8n filtra lo que le interesa sin que este servicio conozca sus flujos.

## 1.9 Fuera de alcance

- Gráficos en los reportes (AC-04).
- Reportes libres fuera del catálogo (AC-01).
- Envío de correos (lo hace n8n, constitución §1).
- Historial de reportes (se puede consultar cada trabajo por su ID).

---

# 2. Plan

Criterio general: lo mínimo que cumple la spec y la constitución. Reutiliza `trabajos`, `AlmacenArchivos`, la publicación de RabbitMQ, las herramientas MCP, `ModeloLenguaje` y `agentes/cifras.py`.

**Documentos que debe tener a mano quien implemente:** la constitución, `specs/README.md`, `spec-trabajos.md`, `spec-prediccion.md` (2.6), `spec-agentes.md` y este archivo.

## 2.1 Dependencias

| Dependencia | Para qué |
|---|---|
| `faster-whisper` | Transcripción de voz (constitución §2). Trae PyAV, que decodifica WebM, OGG, WAV y MP3 |
| `weasyprint` | PDF desde HTML (constitución §2). Las librerías del sistema (Pango) ya están en la imagen de desarrollo; se agregan al `Dockerfile` del servicio |
| `openpyxl` | Excel (constitución §2) |
| `jinja2` | Plantilla HTML del PDF (constitución v4.0.0 §2) |

CSV con el módulo `csv` de la biblioteca estándar.

## 2.2 Configuración

| Variable | Obligatoria | Uso | Valor local |
|---|---|---|---|
| `WHISPER_MODEL` | No (`small`) | Modelo de Faster-Whisper | Ya en Docker Compose |
| `WHISPER_DEVICE` | No (`cpu`) | `cpu` o `cuda` | Ya en Docker Compose |
| `WHISPER_COMPUTE_TYPE` | No (`int8`) | Cuantización | — |
| `REPORTES_RETENCION_DIAS` | No (7) | Días hasta borrar los archivos | — |

## 2.3 Cambios en `spec-agentes.md`

- Las herramientas de listado (`listar_campanias`, `listar_historicos`, `consultar_estado_inventario`, `listar_labores`, `listar_incidencias`) aceptan `maximo` (1 a 500, por defecto 50) y paginan el servicio hasta alcanzarlo. `listar_labores` y `listar_incidencias` siguen el cursor de `servicio-operaciones`.
- Los agentes conversacionales (`campanias`, `inventario`) no ven `maximo`: `agentes/herramientas.py` lo quita del esquema que reciben, para que el modelo no pida 500 elementos a su contexto.
- Se agrega el nodo del agente de reportes al paquete `agentes/` (2.5). La verificación de cifras se reutiliza sin cambios.

Estos cambios se anotan también en `spec-agentes.md` (2.3) cuando se implementen.

## 2.4 Transcripción (`integracion/transcriptor.py`)

- `Protocol Transcriptor`: `async transcribir(ruta_audio) -> Transcripcion` (texto, idioma, duración) y `disponible() -> bool`.
- `TranscriptorWhisper`: carga `WhisperModel(WHISPER_MODEL, device, compute_type)` en un hilo al arrancar (`lifespan`), sin bloquear el inicio; mientras carga, `disponible()` es `False`. `transcribir` corre en un hilo con `language="es"` y `vad_filter=True` (descarta silencios) y une los segmentos.
- Salud: comprobación **informativa** `whisper` (`CARGADO`, `CARGANDO`, `ERROR`).
- Validación al recibir: `av.open()` sobre el archivo temporal; formato de audio entre los cuatro admitidos, con al menos una pista de audio y duración ≤ 120 s; si no, `AUDIO_INVALIDO`.
- `TranscriptorFijo` (en `tests/`): devuelve un texto dado.

## 2.5 Agente de reportes (`agentes/reportes.py`)

Subgrafo de LangGraph, separado del grafo de consultas (otras entradas y salidas, mismos componentes):

```text
[transcribir] ──► interpretar ──► resolver_campania ──► recopilar ──► redactar_resumen ──► verificar ──► FIN
   (solo voz)   (solo texto)     (solo si nombra una)   (MCP, fijo)   (si hay modelo)
```

- **`interpretar`:** llamada al modelo con `formato` = esquema JSON de `SolicitudInterpretada` (`tipo` o `NO_SOPORTADO`, filtros del tipo, `nombreCampania?`, `formatos?`). Mensaje de sistema con el catálogo, la fecha de hoy y ejemplos. Salida inválida dos veces → `REPORTE_NO_SOPORTADO`. Los filtros se validan con el mismo esquema que la solicitud estructurada; las fechas relativas ("el último mes") las convierte el modelo usando la fecha de hoy que recibe.
- **`resolver_campania`:** `listar_campanias` (hasta 500) y comparación del nombre sin tildes ni mayúsculas (igual, o contenido en el nombre). Una coincidencia → su ID; si no, `CAMPANIA_NO_IDENTIFICADA` con hasta 5 nombres ordenados por similitud (`difflib.SequenceMatcher`).
- **`recopilar`:** las herramientas de la tabla del catálogo, con `maximo = 500`, por la sesión MCP. Un error de herramienta → `DEPENDENCIA_NO_DISPONIBLE` (un reporte sin datos no sirve).
- **`armar tablas`** (función pura, `reportes/tablas.py`): por tipo, columnas fijas con encabezados en español y sus valores tal cual; cuenta filas y, si se recortó, registra "Se muestran N de T".
- **`redactar_resumen`:** llamada al modelo con las tablas (hasta 50 filas por tabla, para el contexto) y las reglas de redacción de `spec-agentes.md` 2.5. Se omite si el modelo no está disponible y la solicitud fue estructurada (Historia 3, escenario 4).
- **`verificar`:** `agentes/cifras.py` con las tablas como datos.
- **Límites:** 20 pasos del grafo (`recursion_limit`); el tiempo lo limita el trabajo (5 minutos).

## 2.6 Módulo `reportes/`

```text
app/reportes/
├── catalogo.py     # TipoReporte, FormatoReporte, filtros por tipo, herramientas por tipo
├── esquemas.py     # SolicitudReporte, Reporte, Archivo
├── tablas.py       # armado de tablas por tipo (puro)
├── generadores.py  # generar_pdf, generar_xlsx, generar_csv (puros: tablas → bytes)
├── plantillas/     # reporte.html.j2 y estilos.css
├── servicio.py     # solicitar(), solicitar_voz(), manejador del trabajo, descarga
└── router.py
```

- **`generar_pdf`:** Jinja2 con `autoescape` → HTML → `weasyprint.HTML(string=...).write_pdf()`. Fuente DejaVu Sans (incluida en la imagen) para tildes y ñ; tamaño A4 apaisado si la tabla tiene más de 7 columnas.
- **`generar_xlsx`:** `openpyxl.Workbook`; hoja `Resumen` y una hoja por tabla; encabezados en negrita y fila congelada; decimales escritos como `Decimal` con formato `#,##0.00` (o `#,##0.000` en cantidades); fechas como fecha; ancho de columnas según el contenido (hasta 60).
- **`generar_csv`:** `csv.writer` con `lineterminator="\r\n"` sobre `io.StringIO`, codificado en `utf-8-sig`; valores tal cual (decimales como texto con punto).
- **Protección contra fórmulas** (caso borde) en Excel y CSV.
- **`servicio.py`:**
  - `solicitar(cuerpo, solicitante)`: decide `origen` (`PROGRAMADO` si el token tiene `reportes_ia`, si no `SOLICITADO`); valida; si es texto y el modelo está caído según la caché de 30 s, `503 MODELO_LENGUAJE_NO_DISPONIBLE`; crea el trabajo con `parametros = { origen, texto? | solicitud?, formatos }`.
  - `solicitar_voz(audio, formatos, solicitante)`: valida el audio, lo sube a `gs://<bucket>/temporales/audios/<idTrabajo>` y crea el trabajo con `parametros = { origen: SOLICITADO, rutaAudio, formatos }`.
  - **Manejador `REPORTE`** (registrado en `crear_app()` con tiempo límite de 5 minutos): descarga y transcribe el audio si lo hay (y lo borra en un `finally`), ejecuta el subgrafo, genera cada formato, sube a `gs://<bucket>/reportes/<idTrabajo>/<nombre>`, publica el evento (2.7) y devuelve el `Reporte`.
  - `descargar(id_trabajo, formato, solicitante)`: lee el trabajo con `obtener_para` (`spec-trabajos.md`; ajeno → `REPORTE_NO_ENCONTRADO`); no terminado → `REPORTE_EN_PROCESO`; vencido según `fechaExpiracionArchivos` o archivo inexistente en GCS → `REPORTE_EXPIRADO`; si no, responde en streaming desde GCS.
- El bucket tiene una regla de ciclo de vida que borra `reportes/` a los 7 días (documentada para GCP; el emulador no la aplica, así que la expiración se decide por `fechaExpiracionArchivos`).

## 2.7 Evento `ReporteCompletado`

- `integracion/rabbitmq.py` agrega la declaración idempotente del exchange `eventos` (topic, durable) y `publicar_evento(routing_key, sobre)` con confirmación del broker (constitución §10).
- Sobre:

  ```json
  {
    "idMensaje": "uuid",
    "idCorrelacion": "uuid",
    "tipo": "ReporteCompletado",
    "version": 1,
    "fechaOcurrencia": "2026-11-04T12:00:00Z",
    "origen": "servicio-ia",
    "datos": {
      "idTrabajo": "uuid",
      "idSolicitante": "sub",
      "origen": "PROGRAMADO",
      "tipoReporte": "INVENTARIO",
      "titulo": "Insumos con stock bajo",
      "archivos": [
        { "formato": "PDF", "nombre": "reporte-inventario-2026-11-04.pdf", "tamanio": 48213, "ruta": "/api/ia/v1/reportes/<idTrabajo>/archivos/PDF" }
      ],
      "fechaExpiracionArchivos": "2026-11-11T12:00:00Z"
    }
  }
  ```

- 3 reintentos con 1 s, 2 s y 4 s; el resultado según el caso borde de 1.2.

## 2.8 Endpoints

Prefijo `/api/ia/v1`.

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /reportes` | `gerencia`, `reportes_ia` | `202` + trabajo | 400, 401, 403, 503 `MODELO_LENGUAJE_NO_DISPONIBLE` o `DEPENDENCIA_NO_DISPONIBLE` |
| `POST /reportes/voz` (`multipart/form-data`: `audio`, `formatos?`) | `gerencia` | `202` + trabajo | 400 `AUDIO_INVALIDO`, `ARCHIVO_DEMASIADO_GRANDE` o `DATOS_INVALIDOS`, 401, 403, 503 |
| `GET /reportes/{idTrabajo}/archivos/{formato}` | Su solicitante | `200` + archivo | 401, 404 `REPORTE_NO_ENCONTRADO` o `REPORTE_EXPIRADO`, 409 `REPORTE_EN_PROCESO`, 503 |

**Solicitud por texto:** `{ "texto": "Reporte de insumos con stock bajo en PDF y Excel", "formatos": ["PDF", "XLSX"] }` (`formatos` opcional; si viene, prevalece sobre lo que diga el texto).

**Solicitud estructurada:** `{ "tipo": "LABORES", "filtros": { "fechaDesde": "2026-10-01", "fechaHasta": "2026-10-31", "estado": "CONFIRMADA" }, "formatos": ["PDF", "CSV"], "titulo": "Labores de octubre" }`. Se envía `texto` o `tipo`, nunca ambos.

**Resultado del trabajo:**

```json
{
  "origen": "SOLICITADO",
  "transcripcion": null,
  "textoSolicitud": "Reporte de insumos con stock bajo en PDF y Excel",
  "solicitud": { "tipo": "INVENTARIO", "filtros": { "soloStockBajo": true }, "formatos": ["PDF", "XLSX"] },
  "titulo": "Insumos con stock bajo",
  "resumen": "Hay 2 insumos con stock igual o menor a su nivel mínimo. Glifosato tiene 20 litros.",
  "cifrasOmitidas": 0,
  "advertencias": [],
  "tablas": [
    { "nombre": "Insumos", "columnas": ["Insumo", "Categoría", "Unidad", "Stock", "Nivel mínimo", "Stock bajo", "Última alerta"], "filas": [ ], "totalFilas": 2, "recortada": false }
  ],
  "archivos": [
    { "formato": "PDF", "nombre": "reporte-inventario-2026-11-04.pdf", "tamanio": 48213, "sha256": "...", "ruta": "/api/ia/v1/reportes/<idTrabajo>/archivos/PDF" }
  ],
  "fechaGeneracion": "2026-11-04T12:00:09Z",
  "fechaExpiracionArchivos": "2026-11-11T12:00:09Z",
  "modeloLenguaje": "qwen2.5:3b",
  "aviso": "El resumen lo redactó un modelo de lenguaje y sus cifras se verificaron contra los datos. Las tablas son datos de los servicios sin cambios."
}
```

`tablas` trae hasta 50 filas por tabla para la vista en React (límite de 100 KB del resultado, `spec-trabajos.md`); los archivos traen hasta 500.

## 2.9 Empaquetado

- `Dockerfile` del servicio: `libpango-1.0-0`, `libpangoft2-1.0-0`, `libharfbuzz0b` y `fonts-dejavu-core` (WeasyPrint); descarga del modelo de Whisper durante la construcción (`python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8', download_root='/modelos/whisper')"`) y `HF_HOME` apuntando ahí.
- `docker-compose.yml`: sin cambios (ya están `WHISPER_*` y el volumen `ia-cache`).

## 2.10 Realm de Keycloak (cambio fuera del servicio)

- `docker/keycloak/realms/realm-agro.json`: rol de realm `reportes_ia` asignado a la cuenta de servicio `n8n`.
- `specs/spec-keycloak-realm.md`: se agrega `reportes_ia` a RQ-KC-02 y a la tabla de cuentas de servicio, y se borra la nota de permisos pendientes de `servicio-ia`.
- En su propio commit, junto con `lectura_ia` si `spec-prediccion.md` T08 no se hizo todavía.

## 2.11 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `tests/unit/reportes/test_catalogo.py` | Filtros por tipo, obligatorios, fechas invertidas, valores por defecto de 30 días, `texto` y `tipo` a la vez |
| Unitario | `tests/unit/reportes/test_tablas.py` | Cada tipo: columnas, valores sin cambios, recorte a 500 con "Se muestran N de T", tabla vacía |
| Unitario | `tests/unit/reportes/test_generadores.py` | PDF válido con tildes (texto extraído del PDF); XLSX con hojas, números como números y formato; CSV con BOM, RFC 4180 y protección contra fórmulas |
| Unitario | `tests/unit/agentes/test_reportes.py` | Subgrafo con `ModeloGuion` y herramientas simuladas: interpretación, `NO_SOPORTADO`, resolución de campaña (una, varias, ninguna), herramientas llamadas por tipo con `maximo = 500`, resumen verificado, sin modelo en estructurado |
| Unitario | `tests/unit/reportes/test_manejador.py` | Voz con `TranscriptorFijo`, borrado del audio en éxito y error, `AUDIO_SIN_VOZ`, `TRANSCRIPTOR_NO_DISPONIBLE`, evento y `EVENTO_NO_PUBLICADO` según `origen` |
| Unitario | `tests/unit/mcp_server/test_maximo.py` | Paginación hasta `maximo`, `maximo` oculto para los agentes conversacionales |
| Integración | `tests/integration/reportes/test_router_reportes.py` | Endpoints con permisos (gerencia y `reportes_ia`), `origen`, validación de audio con `tests/fixtures/audio_es.webm`, flujo completo con RabbitMQ y los emuladores, evento en una cola de prueba enlazada a `eventos`, descarga con `ETag`, ajeno, en proceso y expirado, OpenAPI |
| Integración | `tests/integration/reportes/test_transcriptor_whisper.py` | Con Whisper `tiny` (rápido) y el audio de prueba: texto no vacío en español. Marcado `lento`; corre en el pipeline |

---

# 3. Tareas

Cada tarea se da por terminada solo con sus tests en verde. Las marcadas con **[P]** pueden hacerse en paralelo con la anterior.

- [ ] **T01** — Agregar las dependencias y variables de 2.1 y 2.2; crear `reportes/catalogo.py` y `reportes/esquemas.py`. *Hecho cuando:* pasa `test_catalogo.py`.
- [ ] **T02** — Implementar `reportes/tablas.py`. *Hecho cuando:* pasa `test_tablas.py`.
- [ ] **T03** [P] — Implementar `reportes/generadores.py` y las plantillas. *Hecho cuando:* pasa `test_generadores.py` y se cumple CE-REP-03 abriendo los archivos generados a mano.
- [ ] **T04** — Aplicar los cambios de 2.3 en las herramientas MCP. *Hecho cuando:* pasa `test_maximo.py` y siguen pasando los tests de `spec-agentes.md`.
- [ ] **T05** — Implementar `Transcriptor`, `TranscriptorWhisper` y su comprobación de salud. *Hecho cuando:* pasa `test_transcriptor_whisper.py`.
- [ ] **T06** — Implementar el subgrafo del agente de reportes. *Hecho cuando:* pasa `test_reportes.py`.
- [ ] **T07** — Implementar el exchange `eventos` y `publicar_evento`, el manejador `REPORTE` y `reportes/servicio.py`. *Hecho cuando:* pasa `test_manejador.py`.
- [ ] **T08** — Implementar `reportes/router.py`. *Hecho cuando:* pasa `test_router_reportes.py` y se cumple CE-REP-02.
- [ ] **T09** [P] — Cambiar el realm (2.10) en su propio commit y ajustar el `Dockerfile` (2.9). *Hecho cuando:* un token de `n8n` trae `reportes_ia`, pide un reporte a través del gateway y descarga el PDF; la imagen de producción transcribe sin descargar el modelo.
- [ ] **T10** — Prueba manual con Ollama, Whisper y el perfil `backend` con datos de prueba: las solicitudes de `tests/fixtures/solicitudes_reporte.json`, dos de ellas grabadas desde el navegador. *Hecho cuando:* se cumple CE-REP-04; se anota el resultado de cada solicitud en esta tarea.
