Eliges qué datos necesita un reporte que pide la gerencia de una empresa agrícola. Cada fuente es una tabla del reporte.

Fuentes disponibles:

{fuentes}

Reglas:

- Elige las fuentes que la solicitud pide: normalmente una. Elige dos o más solo si pide varias tablas distintas.
- Los costos de **una** campaña nombrada (su lista de costos, sus costos por categoría o sus indicadores) son `COSTOS_CAMPANIA`, `SUBTOTALES_CAMPANIA` o `INDICADORES_CAMPANIA`.
- Comparar varias campañas terminadas por costo, producción o rendimiento es `CAMPANIAS_FINALIZADAS`.
- Si ninguna fuente sirve para la solicitud, devuelve la lista vacía.

Responde solo con JSON: {"fuentes": ["..."]}.
