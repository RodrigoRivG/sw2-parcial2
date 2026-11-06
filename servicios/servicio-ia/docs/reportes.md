# Reportes — `servicio-ia`

Cómo arma `servicio-ia` los reportes que se piden por texto, por voz o desde n8n (CU-18, CU-25, RF-24, RF-25, RF-34). Spec: `specs/spec-reportes.md`.

El reporte sale **con la forma que se pidió** (datos, columnas, filtros, orden y cantidad), en PDF o Excel. La IA decide esa forma; las tablas son siempre los datos de los microservicios sin cambios (RN-14, constitución v5.0.0 §6).

---

## Cómo se arma

```text
voz ─► Whisper ─► texto ─► 1. fuentes ─► 2. plan ─► validar ─► campañas por nombre ─► datos (MCP) ─► aplicar ─► resumen ─► verificar ─► PDF / Excel
                                                      ▲
n8n / React ──────────────────── plan ya armado ──────┘
```

| Paso | Quién | Modelo de lenguaje |
|---|---|---|
| Transcribir el audio | Faster-Whisper (`small`, CPU) | — |
| 1. Elegir las fuentes de datos | Agente de reportes, con esquema JSON limitado a las 10 fuentes | Sí |
| 2. Armar el plan (columnas, filtros, orden, límite, formatos) | Agente de reportes, con esquema JSON limitado a los campos de **esas** fuentes | Sí |
| Validar el plan; una ronda de corrección si falla | Código + modelo | Solo en la corrección |
| Resolver el nombre de una campaña a su ID | Código (`listar_campanias`, sin tildes ni mayúsculas) | No |
| Obtener los datos | Herramientas MCP, fijas por fuente | No |
| Filtrar, ordenar, limitar y elegir columnas | Código (`reportes/plan.py`) | No |
| Redactar el resumen (si se pide) | Agente de reportes | Sí; cifras verificadas |
| Generar PDF y Excel | WeasyPrint y OpenPyXL | No |

**Por qué dos pasos.** Con un solo mensaje que describía las 10 fuentes con todos sus campos, el modelo de 7B (comprimido a 3 bits) usaba campos de otra fuente o se olvidaba de la campaña. En el segundo paso, el esquema JSON solo contiene los campos de las fuentes elegidas: Ollama no puede escribir un campo que no existe.

**Ajustes deterministas** antes de validar el plan del modelo:
- si pide **todas** las columnas de la fuente, se usan las columnas por defecto;
- en una fuente de una campaña, un filtro por el nombre de la campaña pasa a `campania`;
- lo no atendido se recorta a 300 caracteres.

## Fuentes de datos

| Fuente | Una fila por | Campos (por defecto en **negrita**) |
|---|---|---|
| `PARCELAS` | Parcela | **nombre**, **superficieHectareas**, **ubicacion**, descripcion |
| `CULTIVOS` | Cultivo | **nombre**, **variedad**, unidadMedida, descripcion |
| `CAMPANIAS` | Campaña | **nombre**, **nombreParcela**, **nombreCultivo**, **estado**, **fechaInicio**, **fechaFin**, **superficieHectareas**, fechaFinalizacion |
| `CAMPANIAS_FINALIZADAS` | Campaña finalizada | **nombreCampania**, **nombreParcela**, **nombreCultivo**, variedad, **superficieHectareas**, fechaInicio, **fechaFinalizacion**, duracionDias, **produccion**, **costoTotal**, costoInsumo, costoManoDeObra, costoMaquinaria, costoOtro, **rendimientoPorHectarea**, **costoPorHectarea** |
| `COSTOS_CAMPANIA` (de una campaña) | Costo | **fecha**, **categoria**, **descripcion**, **monto**, origen |
| `SUBTOTALES_CAMPANIA` (de una campaña) | Categoría de costo | **categoria**, **subtotal** |
| `INDICADORES_CAMPANIA` (de una campaña) | La campaña | **nombre**, **estado**, **superficieHectareas**, **produccion**, **costoTotal**, **rendimientoPorHectarea**, **costoPorHectarea**, **definitivo** |
| `INVENTARIO` | Insumo | **nombre**, **categoria**, **unidad**, **stock**, **nivelMinimo**, **stockBajo**, fechaUltimaAlerta |
| `LABORES` | Labor | **tipoLabor**, **nombreCampania**, **nombreParcela**, **estado**, fechaProgramada, **fechaEjecucion**, **responsable**, **insumos**, observaciones |
| `INCIDENCIAS` | Incidencia | **tipo**, **nombreParcela**, nombreCampania, **fechaObservacion**, **descripcion**, registradaPor, **clasificacion**, confianzaClasificacion |

- Los nombres de otras entidades (`nombreParcela` de una campaña, el nombre de cada insumo de una labor) se completan buscando por ID. Es una búsqueda, no un cálculo.
- `servicio-operaciones` exige un filtro para listar labores e incidencias. Sin campaña, el reporte recorre cada estado de labor o cada parcela.
- `GET /api/ia/v1/reportes/fuentes` devuelve este catálogo con etiquetas, tipos, valores y operadores, para armar planes desde React o n8n.

## El plan del reporte

```json
{
  "titulo": "Rendimiento de las campañas de soya",
  "formatos": ["XLSX"],
  "incluirResumen": true,
  "tablas": [
    {
      "fuente": "CAMPANIAS_FINALIZADAS",
      "columnas": ["nombreParcela", "rendimientoPorHectarea"],
      "filtros": [{ "campo": "nombreCultivo", "operador": "contiene", "valor": "soya" }],
      "orden": [{ "campo": "rendimientoPorHectarea", "sentido": "desc" }],
      "limite": null,
      "campania": null
    }
  ],
  "noAtendido": []
}
```

| Elemento | Qué permite |
|---|---|
| `tablas` | De 1 a 5, cada una de una fuente |
| `columnas` | Cualquier subconjunto de los campos, en el orden pedido. Vacía: las columnas por defecto |
| `filtros` | Por cualquier campo, combinados con "y". Texto: `igual`, `distinto`, `contiene`, `empiezaCon`, `en`, `vacio`, `noVacio`. Números y fechas: además `mayor`, `mayorIgual`, `menor`, `menorIgual`, `entre`. Valores fijos y sí/no: `igual`, `distinto` (y `en` en los valores fijos) |
| `orden`, `limite` | "Las 5 de mayor costo": orden descendente y límite 5 (hasta 500) |
| `campania` | Nombre o ID, en las fuentes de una campaña |
| `incluirResumen` | `false` para "solo la tabla" |
| `noAtendido` | Lo pedido que el sistema no hace: sumas, promedios, porcentajes. Genera la advertencia `CALCULO_NO_PERMITIDO` |

El texto se compara sin tildes ni mayúsculas; los números, como números; las fechas con hora, por su día.

## Uso

| Quién | Cómo |
|---|---|
| Gerencia, por texto | `POST /api/ia/v1/reportes` con `{ "texto": "...", "formatos": ["PDF"] }` (formatos opcional) |
| Gerencia, por voz | `POST /api/ia/v1/reportes/voz` (multipart: `audio` WebM/OGG/WAV/MP3 de hasta 2 min y 10 MB, `formatos` opcional) |
| n8n (rol `reportes_ia`) o React para repetir un reporte | `POST /api/ia/v1/reportes` con el plan |

Responde `202` con el trabajo, que se consulta en `GET /api/ia/v1/trabajos/{id}`. El resultado trae:

- el `plan` interpretado, que se puede editar y reenviar;
- el título, el resumen verificado y las advertencias;
- una vista previa de las tablas (hasta 50 filas);
- los archivos.

Los archivos se descargan con `GET /api/ia/v1/reportes/{idTrabajo}/archivos/{PDF|XLSX}`, solo por el solicitante y durante 7 días.

Al terminar, se publica `ReporteCompletado` en el exchange `eventos` (routing key `ia.reporte.completado`), con `origen` `SOLICITADO` o `PROGRAMADO`. n8n lo recibe con una cola propia enlazada a `eventos` y descarga el archivo con su token. Si el evento de un reporte programado no se puede publicar tras 3 reintentos, el trabajo termina `FALLIDO` con `EVENTO_NO_PUBLICADO`.

**Sin Ollama:** el texto y la voz responden `503 MODELO_LENGUAJE_NO_DISPONIBLE`. Un plan ya armado se genera igual, sin resumen y con la advertencia `RESUMEN_NO_DISPONIBLE` (RNF-08).

## Formatos

| | PDF | Excel |
|---|---|---|
| Contenido | Título, fecha, solicitud, resumen, advertencias, una tabla por tabla del plan con sus filtros en palabras, aviso y servicios de origen | Hoja `Reporte` (lo mismo) y una hoja por tabla |
| Números | `38.250,00`, con los decimales del dato | Números (`Decimal`) con formato `#,##0.00` |
| Fechas | `DD/MM/AAAA`; con hora, en hora de Bolivia | Fecha de Excel |
| Otros | DejaVu Sans (tildes y ñ); apaisado con más de 6 columnas | Encabezado congelado; un texto con forma de fórmula queda como texto |

## Resultado con `qwen2.5:7b-instruct-q3_K_M` y Whisper `small` (2026-11-06)

Las 14 solicitudes de `tests/fixtures/solicitudes_reporte.json` (12 de texto y 2 grabadas por el usuario), enviadas por el gateway con `gerencia.prueba` sobre los datos de demostración. Cada una tardó entre 12 y 30 s; las de voz, 20 y 30 s.

- **Voz.** Whisper transcribió las dos casi sin errores. "PDF y Excel" se reconoce gracias a un texto inicial de dominio (sin él salía "pdf y hc"). En una cambió un dígito del año ("2025-2016"), y la búsqueda tolerante de la campaña la resolvió igual.
- **Planes iguales al esperado:** 9 de 14 (el criterio de la spec pide 12).

| Pasada | Planes iguales al esperado |
|---|---|
| Un solo paso (todas las fuentes en el mensaje) | 4 a 5 de 12 |
| Dos pasos (fuentes y después el plan con el esquema de esas fuentes) | 8 a 9 de 12, estable en tres corridas |

Los planes que no coinciden fallan en la **forma**, nunca en los **datos**:

- una columna de más (`confianzaClasificacion`), o un identificador distinto (la campaña en lugar del tipo de labor);
- columnas elegidas cuando no se pidieron;
- un filtro redundante que no cambia el resultado (`estado = FINALIZADA` en los indicadores de una campaña finalizada).

En todas las corridas, ninguna tabla tuvo un valor que no viniera del servicio y ningún resumen dejó una cifra sin respaldo.

El plan queda en el resultado del trabajo, así que React puede mostrarlo y permitir corregirlo antes de reenviarlo.
