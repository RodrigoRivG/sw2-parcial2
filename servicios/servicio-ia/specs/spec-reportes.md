# Reportes armados según la solicitud, por texto o voz, y reportes programados — `servicio-ia`

| Campo | Valor |
|---|---|
| Servicio | `servicio-ia` |
| Archivo | `specs/spec-reportes.md` |
| Estado | Implementada (2026-11-06) · pipeline en GitHub pendiente de confirmar |
| Fecha | 2026-11-05 (versión anterior aprobada el 2026-11-04, con catálogo fijo de reportes y CSV) |
| Constitución | v5.0.0 (secciones 1, 2, 4, 6, 7, 9 y 10) |
| Trazabilidad | CU-18, CU-25 · RF-24, RF-25, RF-34 · RN-13, RN-14 · procesos 8 y 11 del documento de requisitos · Módulo 8 (n8n) |
| Depende de | `spec-trabajos.md` (tipo `REPORTE`), `spec-prediccion.md` (`AlmacenArchivos`), `spec-agentes.md` (herramientas MCP con `maximo`, `ModeloLenguaje`, verificación de cifras) |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## 1.1 Contexto

Gerencia pide un reporte escribiendo o hablando y lo recibe **con la forma que pidió**: los datos, las columnas, los filtros, el orden y la cantidad de filas que dijo, en PDF o Excel (CU-18, proceso 8). Por ejemplo: "Quiero una tabla con la parcela y el rendimiento de las campañas de soya finalizadas, de mayor a menor, en Excel". n8n pide reportes periódicos y los envía por correo (CU-25, RF-34, proceso 11).

El documento de requisitos exige que el reporte use "exclusivamente cálculos de los microservicios; el modelo de lenguaje interpreta y redacta, no genera cifras" (RN-14). Por eso el modelo de lenguaje no arma el reporte directamente: arma un **plan del reporte** (qué datos, qué columnas, qué filtros, qué orden), y el código lo ejecuta sobre los datos de los microservicios sin modificar ningún valor (constitución v5.0.0 §6).

| Paso | Quién | Modelo de lenguaje |
|---|---|---|
| 1. Transcribir el audio | Faster-Whisper | — |
| 2. Convertir la solicitud en un **plan del reporte** | Agente de reportes | Sí, con salida en esquema JSON restringido a las fuentes y campos reales. n8n y React pueden enviar el plan ya armado y se saltan este paso |
| 3. Validar el plan y resolver nombres (campañas) a IDs | Código | No |
| 4. Obtener los datos | Herramientas MCP de `spec-agentes.md`, según la fuente de cada tabla (fijo por fuente, no lo elige el modelo) | No |
| 5. Aplicar el plan: filtrar, ordenar, limitar y elegir columnas | Código (funciones puras) | No |
| 6. Redactar el resumen, si el plan lo pide | Agente de reportes | Sí; cifras verificadas con `spec-agentes.md` 2.6 |
| 7. Generar los archivos | WeasyPrint (PDF) y OpenPyXL (Excel) | No |

### Fuentes de datos

Una **fuente** es un conjunto de filas que se obtiene con herramientas MCP. Cada tabla del reporte sale de una fuente. Cada fuente tiene campos con nombre, etiqueta en español y tipo. Los campos `nombre*` de otra entidad (por ejemplo, `nombreParcela` en una campaña) se completan buscando por ID en otra herramienta: es una búsqueda, no un cálculo.

| Fuente | Una fila por | Campos | Herramientas |
|---|---|---|---|
| `PARCELAS` | Parcela | `nombre`, `superficieHectareas`, `ubicacion`, `descripcion` | `listar_parcelas` |
| `CULTIVOS` | Cultivo | `nombre`, `variedad`, `unidadMedida`, `descripcion` | `listar_cultivos` |
| `CAMPANIAS` | Campaña (cualquier estado) | `nombre`, `nombreParcela`, `nombreCultivo`, `estado`, `fechaInicio`, `fechaFin`, `superficieHectareas`, `fechaFinalizacion` | `listar_campanias`, `listar_parcelas`, `listar_cultivos` |
| `CAMPANIAS_FINALIZADAS` | Campaña finalizada | `nombreParcela`, `nombreCultivo`, `variedad`, `superficieHectareas`, `fechaInicio`, `fechaFinalizacion`, `duracionDias`, `produccion`, `costoTotal`, `costoInsumo`, `costoManoDeObra`, `costoMaquinaria`, `costoOtro`, `rendimientoPorHectarea`, `costoPorHectarea` | `listar_historicos` |
| `COSTOS_CAMPANIA` | Costo de **una** campaña | `categoria`, `monto`, `fecha`, `descripcion`, `origen` | `obtener_costos_campania` |
| `SUBTOTALES_CAMPANIA` | Categoría de costo de **una** campaña | `categoria`, `subtotal` | `obtener_costos_campania` |
| `INDICADORES_CAMPANIA` | **Una** campaña (una sola fila) | `nombre`, `estado`, `superficieHectareas`, `produccion`, `costoTotal`, `rendimientoPorHectarea`, `costoPorHectarea`, `definitivo` | `obtener_campania`, `obtener_indicadores_campania` |
| `INVENTARIO` | Insumo | `nombre`, `categoria`, `unidad`, `stock`, `nivelMinimo`, `stockBajo`, `fechaUltimaAlerta` | `consultar_estado_inventario` |
| `LABORES` | Labor | `tipoLabor`, `nombreCampania`, `nombreParcela`, `estado`, `fechaProgramada`, `fechaEjecucion`, `responsable`, `insumos`, `observaciones` | `listar_labores`, `listar_campanias`, `listar_parcelas`, `consultar_estado_inventario` |
| `INCIDENCIAS` | Incidencia | `tipo`, `nombreParcela`, `nombreCampania`, `fechaObservacion`, `descripcion`, `registradaPor`, `clasificacion`, `confianzaClasificacion` | `listar_incidencias`, `listar_parcelas`, `listar_campanias` |

Notas:

- Las fuentes `COSTOS_CAMPANIA`, `SUBTOTALES_CAMPANIA` e `INDICADORES_CAMPANIA` son de una campaña: el plan la indica por nombre o por ID.
- `costoInsumo` … `costoOtro` son los valores de `costosPorCategoria` del histórico, tal como los devuelve `servicio-gestion`.
- `insumos` de una labor es un texto con el nombre, la cantidad y la unidad de cada insumo ("Urea 46 %: 100.000 KILOGRAMO"). Los valores no cambian; solo se unen en un texto.
- `servicio-operaciones` exige un filtro para listar labores (campaña o estado) e incidencias (campaña o parcela). Cuando el plan no filtra por campaña, la fuente recorre lo necesario: labores, cada estado; incidencias, cada parcela. El usuario no ve esa restricción (decisión del 2026-11-05).

### El plan del reporte

```json
{
  "titulo": "Rendimiento de las campañas de soya",
  "formatos": ["XLSX"],
  "incluirResumen": true,
  "tablas": [
    {
      "fuente": "CAMPANIAS_FINALIZADAS",
      "titulo": "Campañas de soya finalizadas",
      "columnas": ["nombreParcela", "rendimientoPorHectarea"],
      "filtros": [{ "campo": "nombreCultivo", "operador": "contiene", "valor": "soya" }],
      "orden": [{ "campo": "rendimientoPorHectarea", "sentido": "desc" }],
      "limite": null
    }
  ],
  "noAtendido": []
}
```

| Elemento | Qué permite | Por defecto |
|---|---|---|
| `tablas` | 1 a 5 tablas, cada una de una fuente | — |
| `columnas` | Cualquier subconjunto de los campos de la fuente, en el orden pedido | Las columnas por defecto de la fuente (2.5) |
| `filtros` | Por cualquier campo: `igual`, `distinto`, `contiene`, `empiezaCon`, `mayor`, `mayorIgual`, `menor`, `menorIgual`, `entre`, `en`, `vacio`, `noVacio`. Se combinan con "y" | Sin filtros |
| `orden` | Uno o más campos, `asc` o `desc` | El orden por defecto de la fuente |
| `limite` | Las primeras N filas después de ordenar ("las 5 de mayor costo") | Hasta 500 |
| `campania` (en la tabla) | Nombre o ID de la campaña, para las fuentes de una campaña | — |
| `incluirResumen` | Si el reporte lleva un texto redactado. `false` si se pide "solo la tabla" | `true` |
| `formatos` | `PDF`, `XLSX` o ambos | `PDF` |
| `noAtendido` | Lo que se pidió y el sistema no hace (un cálculo, un dato que no existe), en palabras del usuario | `[]` |

**Lo que el reporte nunca hace (RN-14):** sumar, promediar, calcular porcentajes, diferencias o columnas nuevas. Si la solicitud lo pide ("el costo promedio por campaña"), el reporte se genera con los datos que sí existen, y `noAtendido` lo informa como advertencia `CALCULO_NO_PERMITIDO`. Contar filas sí está permitido.

Los filtros de texto ignoran tildes y mayúsculas ("soya" encuentra "Soya"). Los filtros por número y fecha comparan el valor como número o fecha, no como texto.

## 1.2 Escenarios de usuario y pruebas

### Historia 1 — Pedir un reporte por texto y recibirlo con la forma pedida (Prioridad: P1)

Como gerencia, quiero describir con mis palabras qué datos, columnas, filtros y orden quiero, y descargar el reporte con exactamente eso (CU-18).

**Por qué esta prioridad:** es el flujo principal; la voz y los programados lo reutilizan.

**Prueba independiente:** con el modelo de lenguaje simulado (`ModeloGuion`, que devuelve el plan) y los servicios simulados.

**Escenarios de aceptación:**

1. **Dado** "Quiero una tabla con la parcela y el rendimiento de las campañas de soya finalizadas, de mayor a menor, en Excel", **cuando** gerencia lo envía a `POST /reportes`, **entonces** recibe `202` con el trabajo. Al terminar, el `resultado` trae:
   - el plan interpretado;
   - una tabla con **solo** las columnas Parcela y Rendimiento por hectárea, solo con campañas de soya, ordenada de mayor a menor;
   - el título, el resumen verificado y `cifrasOmitidas`;
   - una vista previa de las tablas (hasta 50 filas cada una) para React;
   - el archivo XLSX, con nombre, tamaño, SHA-256 y ruta de descarga.
2. **Dado** "Reporte de insumos con stock bajo en PDF y Excel", **entonces** la fuente es `INVENTARIO`, con el filtro `stockBajo igual true`, las columnas por defecto y los dos formatos.
3. **Dado** "Las 3 campañas finalizadas con mayor costo por hectárea, solo nombre de la parcela, cultivo y costo por hectárea", **entonces** el plan tiene esas 3 columnas, orden `costoPorHectarea desc` y `limite = 3`.
4. **Dado** "Campañas finalizadas con costo por hectárea mayor a 2500", **entonces** el filtro compara como número, no como texto.
5. **Dado** "Costos de la campaña Soya verano 2025-2026 Lote Norte, con sus subtotales", **entonces** el reporte tiene dos tablas (`SUBTOTALES_CAMPANIA` y `COSTOS_CAMPANIA`) de la campaña buscada por nombre con `listar_campanias`. Con una sola coincidencia, se usa su ID.
6. **Dado** que el nombre coincide con varias campañas o con ninguna, **entonces** el trabajo termina `FALLIDO` con `CAMPANIA_NO_IDENTIFICADA` y un mensaje con hasta 5 nombres parecidos.
7. **Dado** "Solo la tabla de insumos, sin texto", **entonces** `incluirResumen = false` y el reporte no lleva resumen.
8. **Dado** "El costo promedio de las campañas de soya", **entonces** el reporte se genera con los costos de cada campaña de soya y la advertencia `CALCULO_NO_PERMITIDO` ("El sistema no calcula promedios ni totales propios; se muestran los datos de cada campaña").
9. **Dado** una solicitud que ninguna fuente puede atender ("el clima de mañana"), **entonces** `FALLIDO` con `REPORTE_NO_SOPORTADO` y las fuentes disponibles en el mensaje.
10. **Dado** un plan del modelo que no se puede validar (un campo que no existe en la fuente), **entonces** se le devuelve el error al modelo **una vez** con los campos válidos para que lo corrija; si vuelve a fallar, `FALLIDO` con `REPORTE_NO_SOPORTADO` y el motivo.
11. **Dado** una solicitud sin formato, **entonces** se genera en PDF.
12. **Dado** un reporte sin filas (ningún insumo con stock bajo), **entonces** se genera igual, con la tabla vacía y el resumen "No se encontraron registros para los filtros indicados."
13. **Dado** "Labores de octubre", sin campaña, **entonces** se obtienen recorriendo cada estado de labor y se filtran por fecha.
14. **Dado** un usuario sin `gerencia` ni `reportes_ia`, **entonces** `403 SIN_PERMISO`.

---

### Historia 2 — Pedir un reporte por voz (Prioridad: P1)

Como gerencia, quiero grabar mi solicitud desde React y recibir el reporte, sin escribir (proceso 8).

**Prueba independiente:** con un transcriptor simulado (devuelve un texto fijo) y, en integración, con un audio grabado en `tests/fixtures/`.

**Escenarios de aceptación:**

1. **Dado** un audio WebM (Opus), OGG, WAV o MP3 de hasta 2 minutos y 10 MB, **cuando** gerencia lo envía a `POST /reportes/voz` (con los formatos opcionales), **entonces** recibe `202` con el trabajo, y su `resultado` incluye además la `transcripcion`. A partir de la transcripción, el flujo es el de la Historia 1.
2. **Dado** el audio transcrito, **entonces** se borra del almacenamiento temporal; solo queda la transcripción (constitución §4).
3. **Dado** un audio sin voz reconocible (transcripción vacía), **entonces** `FALLIDO` con `AUDIO_SIN_VOZ`.
4. **Dado** un archivo que no es audio o que dura más de 2 minutos, **entonces** `400 AUDIO_INVALIDO` sin crear el trabajo; más de 10 MB, `400 ARCHIVO_DEMASIADO_GRANDE`.
5. **Dado** que solo `gerencia` pide reportes por voz, **entonces** la cuenta de n8n recibe `403 SIN_PERMISO` en esta ruta.

---

### Historia 3 — Enviar el plan ya armado y recibir el reporte por correo (Prioridad: P1)

Como n8n (o React, para repetir un reporte), quiero enviar el plan del reporte en JSON, enterarme cuando esté listo y descargarlo, para que el reporte programado salga siempre igual (CU-25, RF-34).

**Prueba independiente:** con la cuenta de servicio de n8n simulada (token con su rol) y RabbitMQ.

**Escenarios de aceptación:**

1. **Dado** un plan válido, **cuando** n8n lo envía a `POST /reportes`, **entonces** recibe `202` y no se usa el modelo de lenguaje para interpretar.
2. **Dado** el `plan` del resultado de un reporte anterior, **cuando** se vuelve a enviar, **entonces** se genera un reporte con la misma forma y los datos actuales.
3. **Dado** el reporte terminado, **entonces** se publica en el exchange `eventos` el evento `ReporteCompletado` con routing key `ia.reporte.completado`, el `idCorrelacion` de la solicitud, `origen = PROGRAMADO` y las rutas de descarga (constitución §7).
4. **Dado** el evento, **cuando** n8n descarga el archivo con su token, **entonces** lo recibe (es el solicitante del trabajo).
5. **Dado** un plan con Ollama caído, **entonces** el reporte se genera sin resumen (`resumen = null`, advertencia `RESUMEN_NO_DISPONIBLE`): los datos no dependen del modelo de lenguaje (RNF-08).
6. **Dado** un plan inválido (fuente inexistente, campo que no es de la fuente, operador que no aplica al tipo del campo, fuente de una campaña sin `campania`, más de 5 tablas), **entonces** `400 DATOS_INVALIDOS` con el detalle de cada error, sin crear el trabajo.
7. **Dado** un reporte de gerencia, **entonces** el evento también se publica, con `origen = SOLICITADO`; n8n decide qué hacer con cada origen.

---

### Historia 4 — Descargar los archivos de un reporte (Prioridad: P1)

Como solicitante, quiero descargar cada archivo del reporte mientras esté disponible.

**Escenarios de aceptación:**

1. **Dado** un reporte terminado, **cuando** su solicitante pide `GET /reportes/{idTrabajo}/archivos/{formato}`, **entonces** recibe el archivo con su `Content-Type`, `Content-Disposition: attachment` con el nombre del archivo y `ETag`.
2. **Dado** otro usuario, un trabajo inexistente o un formato no generado, **entonces** `404 REPORTE_NO_ENCONTRADO`.
3. **Dado** un reporte de más de 7 días, **entonces** `404 REPORTE_EXPIRADO` (los archivos se borran a los 7 días; el trabajo dura 30).
4. **Dado** un trabajo que todavía no terminó, **entonces** `409 REPORTE_EN_PROCESO`.

---

### Historia 5 — Ninguna cifra inventada ni calculada (Prioridad: P1)

Como gerencia, quiero que las tablas sean los datos del sistema sin cambios y que el texto no diga cifras que no estén en ellas (RN-14).

**Escenarios de aceptación:**

1. **Dado** los datos de una fuente, **entonces** cada celda tiene exactamente el valor recibido: en Excel como número con el mismo valor; en el PDF con formato de lectura (separador de miles `.` y decimal `,`) sin redondear.
2. **Dado** cualquier plan, **entonces** el reporte no tiene columnas que no sean campos de la fuente ni filas de totales.
3. **Dado** un resumen con una cifra que no está en las tablas, **entonces** esa oración se quita (`spec-agentes.md` 2.6).
4. **Dado** cualquier reporte, **entonces** el PDF y la hoja `Reporte` del Excel dicen qué parte redactó el modelo de lenguaje, que las cifras se verificaron y de qué servicios salieron los datos.

### Casos borde

- **Muchas filas:** cada fuente trae como máximo 500 elementos (`maximo = 500`). Si el servicio tiene más, el reporte lo indica ("Los datos de origen tienen 734 registros; se usaron los 500 más recientes").
- **Filtro sobre un campo vacío:** una fila sin valor no cumple `mayor`, `menor` ni `entre`; sí cumple `vacio`.
- **Textos con caracteres especiales:** en Excel, un texto que empieza con `=`, `+`, `-` o `@` se antepone con `'` para que no se interprete como fórmula. En el PDF, la plantilla escapa el HTML.
- **Nombres de archivo:** `reporte-<título sin tildes ni espacios, hasta 40 caracteres>-<AAAA-MM-DD>.<ext>`.
- **Fechas relativas** ("el último mes", "este año"): las convierte el modelo con la fecha de hoy que recibe en el mensaje de sistema; el plan guarda fechas absolutas.
- **Whisper no está cargado aún** (primer arranque, descargando el modelo): el trabajo de voz espera hasta su tiempo límite y, si no está, `FALLIDO` con `TRANSCRIPTOR_NO_DISPONIBLE`.
- **El evento no se puede publicar** (RabbitMQ caído al terminar): se reintenta 3 veces. Si falla, en un reporte `PROGRAMADO` el trabajo termina `FALLIDO` con `EVENTO_NO_PUBLICADO` (n8n no se enteraría y el correo no saldría); en uno `SOLICITADO`, se registra el error y el trabajo termina `COMPLETADO`.

## 1.3 Requisitos

### Requisitos funcionales

- **RQ-REP-01:** `POST /reportes` acepta texto libre o un plan del reporte, y crea un trabajo `REPORTE` con tiempo límite de 5 minutos.
- **RQ-REP-02:** `POST /reportes/voz` acepta un audio, lo guarda de forma temporal y crea un trabajo `REPORTE` que lo transcribe primero con Faster-Whisper.
- **RQ-REP-03:** el agente de reportes convierte el texto en un plan con salida en esquema JSON limitado a las fuentes y campos del catálogo, con una ronda de corrección si el plan no valida.
- **RQ-REP-04:** el plan se valida contra el catálogo de fuentes con las mismas reglas, venga del modelo o de la solicitud.
- **RQ-REP-05:** los datos se obtienen con las herramientas MCP de cada fuente, a través de una sesión de cliente MCP (como en `spec-agentes.md`), con hasta 500 elementos por herramienta.
- **RQ-REP-06:** el plan se aplica con funciones puras: filtrar, ordenar, limitar y elegir columnas, sin modificar valores ni agregar columnas o filas calculadas.
- **RQ-REP-07:** el resumen se redacta solo si el plan lo pide, y se verifica con la verificación de cifras de `spec-agentes.md`.
- **RQ-REP-08:** se generan los formatos pedidos (`PDF`, `XLSX`) y se guardan en Cloud Storage.
- **RQ-REP-09:** al terminar se publica `ReporteCompletado` (`ia.reporte.completado`) con `origen`.
- **RQ-REP-10:** `GET /reportes/{idTrabajo}/archivos/{formato}` entrega los archivos al solicitante durante 7 días.
- **RQ-REP-11:** la cuenta de servicio de n8n tiene un rol propio, `reportes_ia`, que solo permite `POST /reportes` y descargar sus archivos.

### Entidades clave

- **`PlanReporte`** (esquema): `titulo`, `formatos`, `incluirResumen`, `tablas` (lista de `TablaPlan`: `fuente`, `titulo?`, `columnas`, `filtros`, `orden`, `limite?`, `campania?`), `noAtendido`.
- **`Reporte`** (resultado del trabajo `REPORTE`): `origen` (`SOLICITADO`, `PROGRAMADO`), `transcripcion?`, `textoSolicitud?`, `plan`, `titulo`, `resumen`, `cifrasOmitidas`, `advertencias`, `tablas` (vista previa), `archivos`, `fechaGeneracion`, `fechaExpiracionArchivos`, `modeloLenguaje`.

No hay colecciones nuevas: el reporte vive en el trabajo; los archivos, en Cloud Storage.

## 1.4 Permisos

| Operación | Roles |
|---|---|
| `POST /reportes` (texto o plan) | `gerencia`, `reportes_ia` (cuenta de servicio de n8n) |
| `POST /reportes/voz` | `gerencia` |
| `GET /reportes/fuentes` (catálogo de fuentes y campos, para armar planes en React o n8n) | `gerencia`, `reportes_ia` |
| `GET /reportes/{idTrabajo}/archivos/{formato}` | Su solicitante |
| Consultar el trabajo | Su solicitante (`spec-trabajos.md`) |

`reportes_ia` es un rol de realm nuevo, asignado solo al client `n8n` (2.12).

## 1.5 Errores de esta funcionalidad

| HTTP | Código | Mensaje | Cuándo |
|---|---|---|---|
| 400 | `DATOS_INVALIDOS` | (común) | Texto vacío o de más de 1.000 caracteres; plan inválido (Historia 3, escenario 6); `texto` y `tablas` a la vez; formato inexistente |
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
| `REPORTE_NO_SOPORTADO` | "No se pudo armar el reporte pedido con los datos disponibles: <motivo>. Datos disponibles: parcelas, cultivos, campañas, …" |
| `CAMPANIA_NO_IDENTIFICADA` | "No se pudo identificar la campaña. Campañas parecidas: …" |
| `AUDIO_SIN_VOZ` | "No se reconoció voz en el audio." |
| `TRANSCRIPTOR_NO_DISPONIBLE` | "La transcripción de voz no está disponible en este momento." |
| `EVENTO_NO_PUBLICADO` | "El reporte se generó pero no se pudo notificar. Intente nuevamente." |
| `MODELO_LENGUAJE_NO_DISPONIBLE`, `DEPENDENCIA_NO_DISPONIBLE` y los comunes de `spec-trabajos.md` | — |

Advertencias del resultado (el trabajo termina `COMPLETADO`): `CALCULO_NO_PERMITIDO` (con lo no atendido), `RESUMEN_NO_DISPONIBLE`, `DATOS_RECORTADOS` (la fuente tenía más de 500 registros).

## 1.6 Criterios de éxito

- **CE-REP-01:** los escenarios de las historias 1 a 5 pasan como tests automáticos, sin Ollama ni Whisper reales.
- **CE-REP-02:** un plan de inventario en los dos formatos se genera en menos de 15 s; un reporte por voz de 15 s de audio, en menos de 90 s en el equipo de desarrollo (Whisper `small` en CPU).
- **CE-REP-03:** el PDF se abre en un lector estándar con tildes y ñ correctas; el XLSX se abre en Excel y LibreOffice con números en las celdas numéricas.
- **CE-REP-04:** con Ollama (`qwen2.5:7b-instruct-q3_K_M`) y Whisper reales, las 14 solicitudes de `tests/fixtures/solicitudes_reporte.json` producen el plan esperado en 9 casos o más. Antes eran 12 solicitudes y 10 aciertos; hicieron falta 14 solicitudes para tener una por fuente y cubrir columnas, filtros, orden y límite. El umbral bajó de 12 a 9 por decisión del usuario (2026-11-06): los planes que fallan difieren en la forma (columnas o un filtro redundante), nunca en los datos, y el plan interpretado se puede corregir y reenviar. Hay al menos una por fuente y varias con columnas, filtros, orden y límite; 2 son audios grabados por el usuario. Se considera esperado el plan con las mismas fuentes, columnas, filtros, orden y límite (prueba manual, ver T11).
- **CE-REP-05:** cobertura ≥ 80 % (README D-13), Ruff y mypy sin errores, pipeline en verde.

## 1.7 Supuestos

- El modelo de lenguaje es `qwen2.5:7b-instruct-q3_K_M` (`OLLAMA_MODEL`). La versión Q4 de `qwen2.5:7b` (5,4 GB con un contexto de 8192) no entraba entera en la GPU de 6 GB del equipo de desarrollo, de la que Ollama obtiene unos 4,1 GB: la carga en frío tardaba 91 s y una consulta, hasta 70 s. La Q3 ocupa 4,2 GB, entra entera, carga en 33 s y arma planes JSON con más precisión que el de 3B (medido con las preguntas de `spec-agentes.md` T09). El usuario lo descarga antes de la prueba manual. Las herramientas y el código no dependen del modelo.
- React graba con la MediaRecorder API del navegador, que en Chrome y Edge produce WebM con Opus. El documento de requisitos menciona `.wav` y `.mp3`; se aceptan los cuatro. Los audios de prueba los graba el usuario.
- Faster-Whisper descarga su modelo (`WHISPER_MODEL`, `small`, unos 480 MB) la primera vez y lo guarda en `/cache` (volumen `ia-cache` de Docker Compose). En Cloud Run, el modelo se incluye en la imagen al construirla.
- El flujo de n8n (programación, destinatarios y envío del correo) lo define la spec de n8n. Esta spec fija lo que n8n necesita de este servicio: el plan, el evento y la descarga.
- El realm agrega el rol `reportes_ia` y lo asigna al client `n8n` (ya existe, con la audiencia `servicio-ia`).

## 1.8 Aclaraciones

- **AC-01 — ¿Cómo se cumple RN-14 si la IA decide las columnas y filtros?** La IA solo decide **qué** se muestra: un plan con fuentes, campos, filtros y orden, todos del catálogo. El código lo ejecuta sobre los datos del servicio, sin modificar valores ni calcular nada: filtrar, ordenar, limitar y elegir columnas no generan cifras. El plan queda en el resultado, así que cualquier tabla se puede rastrear hasta su fuente y sus filtros (constitución v5.0.0 §6).
- **AC-02 — ¿Por qué un catálogo de fuentes y no consultas libres a los servicios?** El catálogo define qué herramientas obtienen cada fuente y qué campos tiene, con su tipo. Así el plan se puede validar, el modelo no puede pedir un campo que no existe (el esquema JSON se lo impide) y cada fuente se prueba con datos simulados. Es la diferencia con la spec anterior: el catálogo fijaba **reportes**; ahora fija **datos**, y el reporte lo arma la solicitud.
- **AC-03 — ¿Por qué el plan es también la solicitud estructurada?** n8n necesita reportes iguales cada vez y React puede ofrecer "repetir este reporte". Con un solo formato, lo que interpretó la IA se puede guardar, revisar y volver a enviar sin pasar por la IA.
- **AC-04 — ¿Por qué no hay gráficos?** Ningún requisito los pide en los reportes y React ya grafica con Recharts. Se puede agregar en otra spec.
- **AC-05 — ¿Por qué el evento se publica también para los reportes de gerencia?** La constitución §7 pide publicarlo "al terminar un reporte". Con `origen` en el evento, n8n filtra lo que le interesa sin que este servicio conozca sus flujos.
- **AC-06 — ¿Por qué solo PDF y Excel?** Es lo que pide RF-25. El CSV de la versión anterior se quitó (constitución v5.0.0).
- **AC-07 — ¿Por qué los archivos se descargan a través de la API y no con URL firmadas?** Constitución v4.0.0 §4: el navegador y n8n descargan con el token que ya tienen, solo el solicitante accede y no hace falta CORS en el bucket.

## 1.9 Fuera de alcance

- Cálculos propios: totales, promedios, porcentajes, columnas derivadas (RN-14).
- Gráficos en los reportes (AC-04).
- Cruzar dos fuentes en una sola tabla (por ejemplo, labores con los costos de su campaña); cada tabla sale de una fuente. Sí se completan los nombres de otras entidades por ID (1.1).
- Envío de correos (lo hace n8n, constitución §1).
- Historial de reportes (se puede consultar cada trabajo por su ID).
- Conversación para aclarar la solicitud: si algo no se entiende, el trabajo falla con un mensaje claro.

---

# 2. Plan

Criterio general: lo mínimo que cumple la spec y la constitución. Reutiliza `trabajos`, `AlmacenArchivos`, la conexión a RabbitMQ, las herramientas MCP, `ModeloLenguaje` y `agentes/cifras.py`.

**Documentos que debe tener a mano quien implemente:** la constitución, `specs/README.md`, `spec-trabajos.md`, `spec-prediccion.md` (2.6), `spec-agentes.md` y este archivo.

## 2.1 Dependencias

| Dependencia | Grupo | Para qué |
|---|---|---|
| `faster-whisper` | Principal | Transcripción de voz (constitución §2). Trae PyAV, que decodifica WebM, OGG, WAV y MP3 |
| `weasyprint` | Principal | PDF desde HTML (constitución §2). Las librerías del sistema (Pango, HarfBuzz) y la fuente DejaVu ya están en la imagen de desarrollo; se agregan al `Dockerfile` del servicio |
| `openpyxl` | Principal | Excel (constitución §2) |
| `jinja2` | Principal | Plantilla HTML del PDF (constitución §2) |
| `pypdf` | `dev` | Extraer el texto del PDF en los tests |

## 2.2 Configuración

| Variable | Obligatoria | Uso | Valor local |
|---|---|---|---|
| `WHISPER_MODEL` | No (`small`) | Modelo de Faster-Whisper | Ya en Docker Compose |
| `WHISPER_DEVICE` | No (`cpu`) | `cpu` o `cuda` | Ya en Docker Compose |
| `WHISPER_COMPUTE_TYPE` | No (`int8`) | Cuantización | — |
| `REPORTES_RETENCION_DIAS` | No (7) | Días hasta borrar los archivos | — |
| `OLLAMA_MODEL` | Sí (de `spec-agentes.md`) | Pasa a `qwen2.5:7b-instruct-q3_K_M` | Ya en `.env` (2026-11-06) |

## 2.3 Cambios en las herramientas MCP (`spec-agentes.md`)

`maximo` (1 a 500) ya está implementado en `listar_campanias`, `listar_historicos`, `consultar_estado_inventario`, `listar_labores` y `listar_incidencias`, y oculto para los agentes conversacionales. Se agrega a:

- `listar_parcelas` y `listar_cultivos`, para completar nombres por ID con todas las parcelas y cultivos;
- `obtener_costos_campania`, que hoy trae los primeros 50 costos: con `maximo`, pagina hasta alcanzarlo.

Sin otros cambios: las fuentes usan las herramientas tal como están.

## 2.4 Transcripción (`integracion/transcriptor.py`)

- `Protocol Transcriptor`: `async transcribir(ruta_audio) -> Transcripcion` (texto, idioma, duración) y `disponible() -> bool`.
- `TranscriptorWhisper`: carga `WhisperModel(WHISPER_MODEL, device, compute_type, download_root="/cache/whisper")` en un hilo al arrancar (`lifespan`), sin bloquear el inicio; mientras carga, `disponible()` es `False`. `transcribir` corre en un hilo con `language="es"` y `vad_filter=True` (descarta silencios) y une los segmentos.
- Salud: comprobación **informativa** `whisper` (`UP` si está cargado).
- Validación al recibir: `av.open()` sobre el archivo temporal; formato entre los cuatro admitidos, con al menos una pista de audio y duración ≤ 120 s; si no, `AUDIO_INVALIDO`.
- `TranscriptorFijo` (en `tests/`): devuelve un texto dado.

## 2.5 Catálogo de fuentes (`reportes/fuentes.py`)

Cada fuente se declara una vez y de ahí salen el esquema JSON del plan, la validación, el catálogo de `GET /reportes/fuentes` y el mensaje de sistema del agente:

- `Campo`: `nombre`, `etiqueta` (encabezado en español), `tipo` (`TEXTO`, `DECIMAL`, `ENTERO`, `FECHA`, `FECHA_HORA`, `BOOLEANO`, `ENUM` con sus valores), `por_defecto` (si va en las columnas por defecto).
- `Fuente`: `nombre`, `descripcion` (para el modelo), `campos`, `orden_por_defecto`, `de_una_campania` (bool) y `obtener(sesion_mcp, plan_tabla) -> DatosFuente` (filas como diccionarios con los valores tal cual, más el `total` de origen).
- Cada `obtener` traduce los filtros que el servicio sabe aplicar (estado, fechas, categoría, `soloStockBajo`, tipo) a parámetros de la herramienta para traer menos datos. Igual se vuelven a aplicar en código, así el resultado no depende de esa traducción.
- Completar nombres por ID: un diccionario `id → nombre` por consulta (parcelas, cultivos, campañas, insumos), que se pide una sola vez por reporte.
- Recorridos de operaciones: `LABORES` sin `idCampania` llama a `listar_labores` por cada `EstadoLabor` (o solo por el estado filtrado); `INCIDENCIAS` sin campaña llama a `listar_incidencias` por cada parcela (o solo por la filtrada).

| Fuente | Columnas por defecto | Orden por defecto |
|---|---|---|
| `PARCELAS` | nombre, superficie, ubicación | nombre ↑ |
| `CULTIVOS` | nombre, variedad | nombre ↑ |
| `CAMPANIAS` | nombre, parcela, cultivo, estado, inicio, fin, superficie | inicio ↓ |
| `CAMPANIAS_FINALIZADAS` | parcela, cultivo, superficie, finalización, producción, costo total, rendimiento por ha, costo por ha | finalización ↓ |
| `COSTOS_CAMPANIA` | fecha, categoría, descripción, monto | fecha ↑ |
| `SUBTOTALES_CAMPANIA` | categoría, subtotal | categoría ↑ |
| `INDICADORES_CAMPANIA` | todas | — |
| `INVENTARIO` | nombre, categoría, unidad, stock, nivel mínimo, stock bajo | nombre ↑ |
| `LABORES` | tipo, campaña, parcela, estado, ejecución, responsable, insumos | ejecución ↓ |
| `INCIDENCIAS` | tipo, parcela, fecha, descripción, clasificación | fecha ↓ |

## 2.6 Plan y su aplicación (`reportes/plan.py`)

- **`PlanReporte` y `TablaPlan`** (Pydantic, `ModeloEntrada`): la estructura de 1.1.
- **`validar(plan) -> list[DetalleError]`** (pura): fuente existente, columnas y campos de filtros y orden de la fuente, operador compatible con el tipo (`contiene` solo en texto; `mayor`/`menor`/`entre` en números y fechas; `entre` con dos valores, `en` con una lista), valor convertible al tipo, `campania` presente solo en las fuentes de una campaña, 1 a 5 tablas y `limite` de 1 a 500. Los errores llevan la ruta (`tablas[0].columnas[1]`) y los valores válidos.
- **`aplicar(tabla_plan, datos) -> Tabla`** (pura), en este orden: filtrar, ordenar (vacíos al final), limitar y proyectar las columnas. El texto se compara sin tildes ni mayúsculas, los decimales como `Decimal` y las fechas como fecha. Los valores de las celdas no se tocan.
- **`esquema_json()`**: el esquema del plan con `fuente` y los nombres de campo como enumeraciones, para el `formato` de Ollama. Restringe a campos que existen en **alguna** fuente; la pertenencia a la fuente de la tabla la verifica `validar`.

## 2.7 Agente de reportes (`agentes/reportes.py`)

Subgrafo de LangGraph, separado del grafo de consultas (otras entradas y salidas, mismos componentes):

```text
[transcribir] ─► [interpretar ⇄ corregir] ─► resolver_campanias ─► recopilar ─► aplicar ─► [redactar] ─► verificar ─► FIN
  (solo voz)        (solo texto)                (si hay campania)                          (si incluirResumen)
```

- **`interpretar`:** llamada al modelo con `formato = esquema_json()`. El mensaje de sistema (`prompts/reportes.md`) lleva:
  - el catálogo de fuentes con sus campos, etiquetas y tipos;
  - los operadores y la fecha de hoy;
  - las reglas: solo campos del catálogo, no inventar filtros que no se pidieron, `noAtendido` para los cálculos;
  - 4 ejemplos de solicitud y su plan.
- **`corregir`:** si `validar` devuelve errores, una sola llamada más con los errores y los valores válidos. Si sigue inválido o no tiene tablas, `REPORTE_NO_SOPORTADO` con el motivo.
- **`resolver_campanias`:** para cada tabla con `campania` que no es un UUID: `listar_campanias` (hasta 500) y comparación del nombre sin tildes ni mayúsculas (igual, o contenido en el nombre). Una coincidencia → su ID. Si no, `CAMPANIA_NO_IDENTIFICADA` con hasta 5 nombres ordenados por similitud (`difflib.SequenceMatcher`).
- **`recopilar`:** `Fuente.obtener` de cada tabla, con `maximo = 500`, por la sesión MCP. Un error de herramienta → `DEPENDENCIA_NO_DISPONIBLE` (un reporte con datos incompletos no sirve).
- **`aplicar`:** `plan.aplicar` por tabla; registra `DATOS_RECORTADOS` si el total de origen superaba lo obtenido.
- **`redactar`:** si `incluirResumen` y el modelo está disponible. Recibe las tablas ya aplicadas (hasta 50 filas cada una, para el contexto), la solicitud y las reglas de redacción de `spec-agentes.md` (2 a 5 oraciones, solo cifras de las tablas). Con Ollama caído y un plan enviado ya armado: `resumen = null` y `RESUMEN_NO_DISPONIBLE`.
- **`verificar`:** `agentes/cifras.py` con las tablas como datos.
- **Límites:** 20 pasos del grafo; el tiempo lo limita el trabajo (5 minutos).

## 2.8 Módulo `reportes/`

```text
app/reportes/
├── fuentes.py      # catálogo de fuentes, campos y cómo se obtiene cada una (2.5)
├── plan.py         # PlanReporte, validar, aplicar, esquema_json (puros, 2.6)
├── esquemas.py     # solicitud (texto o plan), Reporte, Archivo
├── generadores.py  # generar_pdf, generar_xlsx (puros: tablas → bytes)
├── plantillas/     # reporte.html.j2 y estilos.css
├── servicio.py     # solicitar(), solicitar_voz(), manejador del trabajo, descarga
└── router.py
```

- **`generar_pdf`:** Jinja2 con `autoescape` → HTML → `weasyprint.HTML(string=...).write_pdf()`. Lleva:
  - título, fecha de generación y la solicitud (el texto o la transcripción);
  - los filtros en palabras ("Cultivo contiene «soya»");
  - el resumen, las advertencias y una tabla por cada tabla del plan;
  - un pie con el aviso y los servicios de origen.

  Fuente DejaVu Sans para tildes y ñ. A4 vertical, o apaisado si alguna tabla tiene más de 6 columnas. Decimales con separador de miles `.` y decimal `,`, con los mismos decimales que el dato; fechas `DD/MM/AAAA`.
- **`generar_xlsx`:** `openpyxl.Workbook`:
  - una hoja `Reporte` con título, solicitud, filtros, resumen, advertencias y aviso, y una hoja por tabla, con el título de la tabla como nombre (hasta 31 caracteres);
  - encabezados en negrita y fila congelada;
  - decimales como `Decimal`, con formato `#,##0.00` (o `#,##0.000` en cantidades de stock); fechas como fecha;
  - ancho de columnas según el contenido (hasta 60);
  - protección contra fórmulas (casos borde).
- **`servicio.py`:**
  - `solicitar(cuerpo, solicitante)`:
    - decide `origen`: `PROGRAMADO` si el token tiene `reportes_ia`; si no, `SOLICITADO`;
    - valida el plan si viene armado (`400` con los detalles);
    - si es texto y el modelo está caído según la caché de 30 s, responde `503 MODELO_LENGUAJE_NO_DISPONIBLE`;
    - crea el trabajo con `parametros = { origen, texto? | plan?, formatos? }`.
  - `solicitar_voz(audio, formatos, solicitante)`: valida el audio, lo sube a `gs://<bucket>/temporales/audios/<uuid>` y crea el trabajo con `parametros = { origen: SOLICITADO, rutaAudio, formatos? }`.
  - **Manejador `REPORTE`** (registrado en `crear_app()` con tiempo límite de 5 minutos):
    1. descarga y transcribe el audio si lo hay, y lo borra en un `finally`;
    2. ejecuta el subgrafo;
    3. genera cada formato y lo sube a `gs://<bucket>/reportes/<idTrabajo>/<nombre>`;
    4. publica el evento (2.9) y devuelve el `Reporte`.
  - `descargar(id_trabajo, formato, solicitante)`:
    - lee el trabajo con `obtener_para` (`spec-trabajos.md`); si es ajeno, `REPORTE_NO_ENCONTRADO`;
    - si no terminó, `REPORTE_EN_PROCESO`;
    - si venció según `fechaExpiracionArchivos` o el archivo no existe en GCS, `REPORTE_EXPIRADO`;
    - si no, responde con el archivo.
- El bucket tiene una regla de ciclo de vida que borra `reportes/` a los 7 días (documentada para GCP; el emulador no la aplica, así que la expiración se decide por `fechaExpiracionArchivos`).

## 2.9 Evento `ReporteCompletado`

- `integracion/rabbitmq.py` agrega la declaración idempotente del exchange `eventos` (topic, durable) y `publicar_evento(routing_key, sobre)` con confirmación del broker (constitución §10).
- Sobre:

  ```json
  {
    "idMensaje": "uuid",
    "idCorrelacion": "uuid",
    "tipo": "ReporteCompletado",
    "version": 1,
    "fechaOcurrencia": "2026-11-05T12:00:00Z",
    "origen": "servicio-ia",
    "datos": {
      "idTrabajo": "uuid",
      "idSolicitante": "sub",
      "origen": "PROGRAMADO",
      "titulo": "Insumos con stock bajo",
      "archivos": [
        { "formato": "PDF", "nombre": "reporte-insumos-con-stock-bajo-2026-11-05.pdf", "tamanio": 48213, "ruta": "/api/ia/v1/reportes/<idTrabajo>/archivos/PDF" }
      ],
      "fechaExpiracionArchivos": "2026-11-12T12:00:00Z"
    }
  }
  ```

- 3 reintentos con 1 s, 2 s y 4 s; el resultado según el caso borde de 1.2.

## 2.10 Endpoints

Prefijo `/api/ia/v1`.

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /reportes` | `gerencia`, `reportes_ia` | `202` + trabajo | 400, 401, 403, 503 `MODELO_LENGUAJE_NO_DISPONIBLE` o `DEPENDENCIA_NO_DISPONIBLE` |
| `POST /reportes/voz` (`multipart/form-data`: `audio`, `formatos?`) | `gerencia` | `202` + trabajo | 400 `AUDIO_INVALIDO`, `ARCHIVO_DEMASIADO_GRANDE` o `DATOS_INVALIDOS`, 401, 403, 503 |
| `GET /reportes/fuentes` | `gerencia`, `reportes_ia` | `200` + fuentes con sus campos, etiquetas, tipos y operadores | 401, 403 |
| `GET /reportes/{idTrabajo}/archivos/{formato}` | Su solicitante | `200` + archivo | 401, 404 `REPORTE_NO_ENCONTRADO` o `REPORTE_EXPIRADO`, 409 `REPORTE_EN_PROCESO`, 503 |

**Solicitud por texto:** `{ "texto": "Las 3 campañas finalizadas con mayor costo por hectárea en PDF", "formatos": ["PDF"] }` (`formatos` opcional; si viene, prevalece sobre lo que diga el texto).

**Solicitud con el plan:** el `PlanReporte` de 1.1 como cuerpo. Se envía `texto` o `tablas`, nunca ambos.

**Resultado del trabajo:**

```json
{
  "origen": "SOLICITADO",
  "transcripcion": null,
  "textoSolicitud": "Quiero una tabla con la parcela y el rendimiento de las campañas de soya finalizadas, de mayor a menor, en Excel",
  "plan": { "titulo": "Rendimiento de las campañas de soya", "formatos": ["XLSX"], "incluirResumen": true, "tablas": [ ], "noAtendido": [] },
  "titulo": "Rendimiento de las campañas de soya",
  "resumen": "La campaña de soya con mayor rendimiento fue la de Lote Norte, con 2800.00 kg/ha.",
  "cifrasOmitidas": 0,
  "advertencias": [],
  "tablas": [
    {
      "titulo": "Campañas de soya finalizadas",
      "fuente": "CAMPANIAS_FINALIZADAS",
      "columnas": [{ "campo": "nombreParcela", "etiqueta": "Parcela" }, { "campo": "rendimientoPorHectarea", "etiqueta": "Rendimiento (kg/ha)" }],
      "filas": [["Lote Norte", "2800.00"], ["Lote Sur", "2400.00"]],
      "totalFilas": 2,
      "totalOrigen": 3
    }
  ],
  "archivos": [
    { "formato": "XLSX", "nombre": "reporte-rendimiento-de-las-campanas-de-soya-2026-11-05.xlsx", "tamanio": 7350, "sha256": "...", "ruta": "/api/ia/v1/reportes/<idTrabajo>/archivos/XLSX" }
  ],
  "fechaGeneracion": "2026-11-05T12:00:09Z",
  "fechaExpiracionArchivos": "2026-11-12T12:00:09Z",
  "modeloLenguaje": "qwen2.5:7b-instruct-q3_K_M",
  "aviso": "El plan y el resumen los produjo un modelo de lenguaje; las cifras del resumen se verificaron contra las tablas. Las tablas son datos de los servicios sin cambios."
}
```

`tablas` trae hasta 50 filas por tabla para la vista en React (límite de 100 KB del resultado, `spec-trabajos.md`); los archivos traen todas las filas (hasta 500).

## 2.11 Empaquetado

- `Dockerfile` del servicio:
  - `libpango-1.0-0`, `libpangoft2-1.0-0`, `libharfbuzz0b` y `fonts-dejavu-core` (WeasyPrint);
  - descarga del modelo de Whisper durante la construcción (`python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8', download_root='/modelos/whisper')"`) y `WHISPER_DOWNLOAD_ROOT` apuntando ahí.
- `docker-compose.yml`: sin cambios (ya están `WHISPER_*` y el volumen `ia-cache`).

## 2.12 Realm de Keycloak (cambio fuera del servicio)

- `docker/keycloak/realms/realm-agro.json`: rol de realm `reportes_ia` asignado a la cuenta de servicio `n8n`.
- `scripts/verificar-realm.py` y `specs/spec-keycloak-realm.md`: se agrega `reportes_ia` (RQ-KC-02 y la tabla de cuentas de servicio).
- En el Keycloak local se aplica con la API de administración, sin borrar el realm (como `lectura_ia` en `spec-prediccion.md` T08).
- En su propio commit.

## 2.13 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `tests/unit/reportes/test_plan.py` | `validar`: cada regla con su ruta de error y valores válidos. `aplicar`: cada operador por tipo, texto sin tildes ni mayúsculas, números como número, fechas, vacíos, orden con vacíos al final, límite, proyección de columnas en el orden pedido, valores sin cambios. `esquema_json` con las fuentes y campos |
| Unitario | `tests/unit/reportes/test_fuentes.py` | Cada fuente con las herramientas simuladas (respuestas de `tests/fixtures/servicios/`): campos y valores tal cual, nombres completados por ID, filtros traducidos a parámetros, recorridos de labores e incidencias, `maximo = 500` |
| Unitario | `tests/unit/reportes/test_generadores.py` | PDF válido con tildes (texto extraído con `pypdf`), solo las columnas del plan, formato de números y apaisado; XLSX con hojas, solo las columnas del plan, números como números y formato, protección contra fórmulas |
| Unitario | `tests/unit/agentes/test_reportes.py` | Subgrafo con `ModeloGuion` y herramientas simuladas: los escenarios 1 a 13 de la Historia 1, ronda de corrección, plan ya armado sin modelo, resumen verificado, `incluirResumen = false`, `CALCULO_NO_PERMITIDO` |
| Unitario | `tests/unit/reportes/test_manejador.py` | Voz con `TranscriptorFijo`, borrado del audio en éxito y error, `AUDIO_SIN_VOZ`, `TRANSCRIPTOR_NO_DISPONIBLE`, evento y `EVENTO_NO_PUBLICADO` según `origen` |
| Unitario | `tests/unit/mcp_server/test_maximo.py` | `maximo` en `listar_parcelas`, `listar_cultivos` y `obtener_costos_campania`; oculto para los agentes conversacionales |
| Integración | `tests/integration/reportes/test_router_reportes.py` | Endpoints con permisos (gerencia y `reportes_ia`), `origen`, plan inválido con detalles, `GET /reportes/fuentes`, validación de audio, flujo completo con RabbitMQ y los emuladores, evento en una cola de prueba enlazada a `eventos`, descarga con `ETag`, ajeno, en proceso y expirado, OpenAPI |
| Integración | `tests/integration/reportes/test_transcriptor_whisper.py` | Con Whisper `tiny` (rápido) y el audio grabado por el usuario: texto no vacío en español. Marcado `lento`; corre en el pipeline |

## 2.14 Notas de implementación (2026-11-06)

- **Módulos.** La declaración del catálogo quedó en `reportes/catalogo.py`, separada de la obtención (`reportes/fuentes.py`), para que `plan.py` no dependa de MCP. El subgrafo quedó en `reportes/agente.py` y no en `agentes/`: la constitución (§3) permite que `reportes` use `agentes`, no al revés. Los mensajes de sistema están en `reportes/prompts/` y la plantilla en `reportes/plantillas/`.
- **Interpretación en dos pasos** (cambio de 2.7). Con un solo mensaje que describía las 10 fuentes con sus campos, el modelo usaba campos de otra fuente o se olvidaba de la campaña: 4 a 5 de 12 planes correctos. Ahora son dos llamadas:
  1. elegir las fuentes (`prompts/fuentes.md`, esquema con las 10 fuentes);
  2. armar el plan con un esquema que solo contiene los campos de esas fuentes (`esquema_json(fuentes)`).

  Así el modelo no puede escribir un campo inexistente. Resultado: 8 a 9 de 12, estable.
- **Ajustes deterministas** del plan del modelo antes de validarlo (`agente.ajustar`):
  - todas las columnas de la fuente equivalen a las columnas por defecto;
  - en una fuente de una campaña, un filtro por su nombre pasa a `campania`;
  - `noAtendido` se recorta a 5 textos de 300 caracteres.
- **La transcripción la hace el manejador**, antes del grafo, porque es el que maneja el archivo temporal. `WHISPER_ACTIVO` (por defecto verdadero) permite que los tests no descarguen el modelo; desactivado, un reporte por voz falla con `TRANSCRIPTOR_NO_DISPONIBLE`. MediaRecorder graba WebM sin duración en la cabecera: se toma del último paquete.
- **Protección contra fórmulas en Excel:** los textos se guardan con tipo texto explícito en vez de anteponer `'`, porque openpyxl escribiría el apóstrofo literal.
- **PDF:** los estilos se insertan sin el autoescape de Jinja (rompía las comillas de la fuente dentro de `<style>`), y el título se escapa como texto CSS para que no pueda cerrar el `<style>`. Los filtros se describen como se muestran las celdas ("Stock bajo es «Sí»").
- **Empaquetado:** además de lo previsto, `libharfbuzz-subset0` (WeasyPrint avisa que lo exigirá). El pipeline instala Pango, HarfBuzz y DejaVu en el runner para los tests del PDF.
- **Campaña por nombre tolerante a la voz.** Si ninguna campaña coincide exactamente, se acepta la más parecida solo si la similitud es al menos 0,9 y le saca 0,05 a la segunda. Whisper transcribió "2025-2016" en lugar de "2025-2026". Antes de comparar se quitan tildes, mayúsculas y puntuación.
- **Tests:** `test_agente.py` y `test_manejador.py` quedaron en `tests/unit/reportes/`. La cola de prueba enlazada a `eventos` es durable: RabbitMQ 4 no admite colas transitorias compartidas.

---

# 3. Tareas

Cada tarea se da por terminada solo con sus tests en verde. Las marcadas con **[P]** pueden hacerse en paralelo con la anterior.

- [x] **T01** — Agregar las dependencias y variables de 2.1 y 2.2; implementar `reportes/fuentes.py` (solo la declaración de campos) y `reportes/plan.py`. *Hecho cuando:* pasa `test_plan.py`. Hecho (2026-11-06): 35 tests en `test_plan.py`.
- [x] **T02** — Aplicar los cambios de 2.3 en las herramientas MCP. *Hecho cuando:* pasa `test_maximo.py` y siguen pasando los tests de `spec-agentes.md`. Hecho: `test_maximo.py`; siguen pasando los de agentes.
- [x] **T03** — Implementar la obtención de cada fuente (2.5). *Hecho cuando:* pasa `test_fuentes.py`. Hecho: 10 tests en `test_fuentes.py`.
- [x] **T04** [P] — Implementar `reportes/generadores.py` y las plantillas. *Hecho cuando:* pasa `test_generadores.py` y se cumple CE-REP-03 abriendo los archivos generados a mano. Hecho: `test_generadores.py`. CE-REP-03 verificado: el usuario abrió el PDF y el Excel de muestra.
- [x] **T05** — Implementar `Transcriptor`, `TranscriptorWhisper` y su comprobación de salud. *Hecho cuando:* pasa `test_transcriptor_whisper.py` con el audio grabado por el usuario. Hecho (2026-11-06) con `costos.ogg` y `campanias.ogg`, grabados por el usuario (OGG Opus, de 7,1 y 4,9 s). Se encontró que `faster-whisper` 1.2.1 llama a `av.open` con un argumento que PyAV 19 ya no admite, así que el audio se decodifica en `transcriptor.decodificar` (16 kHz, mono). Se agregó un texto inicial de dominio: sin él, "PDF y Excel" salía "pdf y hc".
- [x] **T06** — Implementar el subgrafo del agente de reportes y su mensaje de sistema. *Hecho cuando:* pasa `test_reportes.py`. Hecho, con la interpretación en dos pasos (2.14): `test_agente.py`.
- [x] **T07** — Implementar el exchange `eventos` y `publicar_evento`, el manejador `REPORTE` y `reportes/servicio.py`. *Hecho cuando:* pasa `test_manejador.py`. Hecho: `test_manejador.py` (incluye WebM sin duración generado con PyAV).
- [x] **T08** — Implementar `reportes/router.py`. *Hecho cuando:* pasa `test_router_reportes.py` y se cumple CE-REP-02. Hecho: `test_router_reportes.py`. CE-REP-02, parte del plan: el plan de inventario en PDF y Excel tarda menos de 15 s de punta a punta. La parte de voz se mide en T11.
- [x] **T09** [P] — Cambiar el realm (2.12) en su propio commit y ajustar el `Dockerfile` (2.11). *Hecho cuando:* un token de `n8n` trae `reportes_ia`, envía un plan a través del gateway y descarga el PDF; la imagen de producción transcribe sin descargar el modelo. Hecho: `reportes_ia` en el realm, en `verificar-realm.py` (57 correctas) y en `spec-keycloak-realm.md`; aplicado al Keycloak local con la API de administración. Un token de `n8n` envió un plan por el gateway y descargó el PDF. `Dockerfile` con las librerías de WeasyPrint y el modelo de Whisper incluido; el pipeline construye la imagen.
- [x] **T10** [P] — Escribir `tests/fixtures/solicitudes_reporte.json` (12 solicitudes con su plan esperado) y `docs/reportes.md` (fuentes, plan, ejemplos, límites y cómo usarlo desde React y n8n). Hecho: `tests/fixtures/solicitudes_reporte.json` (14 solicitudes) y `docs/reportes.md`.
- [x] **T11** — Prueba manual con `qwen2.5:7b-instruct-q3_K_M`, Whisper `small` y el perfil `backend` con datos de demostración: las 12 solicitudes por el gateway con `gerencia.prueba`, 2 de ellas con los audios grabados. *Hecho cuando:* se cumple CE-REP-04; se anota el resultado de cada solicitud en esta tarea. *Resultado (2026-11-06):* 9 de 14 planes iguales al esperado, incluidas las 2 de voz; CE-REP-04 se cumple con el umbral de 9 de 14 que aceptó el usuario. Los 5 restantes difieren en la forma (columnas o un filtro redundante), nunca en los datos. Detalle en `docs/reportes.md`. Los reportes por voz tardaron 20 y 30 s (CE-REP-02).
