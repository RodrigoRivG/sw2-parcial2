# Respuestas de ejemplo de los otros servicios

Copiadas de los ejemplos de respuesta de cada spec, para los tests de contrato de las herramientas MCP (`spec-agentes.md` 2.10). Los marcadores `"uuid"` y `"6f1c…"` se reemplazaron por UUID válidos, porque las herramientas validan los parámetros.

| Archivo | Origen |
|---|---|
| `parcela.json` | `servicio-gestion/specs/spec-parcelas.md` (respuesta de `GET /parcelas/{id}`) |
| `cultivo.json` | `servicio-gestion/specs/spec-cultivos.md` (solicitud de creación, con `id` y `version` agregados) |
| `campania.json` | `servicio-gestion/specs/spec-campanias.md` (`GET /campanias/{id}` con `resumen`) |
| `costos.json` | `servicio-gestion/specs/spec-costos-manuales.md` (`GET /campanias/{id}/costos`, con un costo agregado en `items` según `CostoRespuesta`) |
| `indicadores.json` | `servicio-gestion/specs/spec-indicadores.md` (campaña finalizada) |
| `historico.json` | `servicio-gestion/specs/spec-consultas-integracion.md` (un elemento de `GET /campanias/historicos`) |
| `estado_inventario.json` | `servicio-inventario/specs/spec-estado-inventario.md` |
| `insumo.json` | `servicio-inventario/specs/spec-insumos.md` |
| `labor.json` | `servicio-operaciones/specs/spec-labores.md` |
| `incidencia.json` | `servicio-operaciones/specs/spec-incidencias.md` |

Los formatos de página (`{ items, pagina, tamanio, total }` en gestión e inventario, `{ items, siguienteCursor }` en operaciones) se verificaron contra el código de cada servicio (`spec-agentes.md` 2.3).
