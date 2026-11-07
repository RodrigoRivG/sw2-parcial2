import type { RequestHandler } from 'express';

/** Orígenes de Apollo Sandbox y Studio, solo fuera de producción (spec-consultas.md 2.5, D-GQL-07). */
export const ORIGENES_APOLLO = new Set(['https://sandbox.embed.apollographql.com', 'https://studio.apollographql.com']);

/**
 * El servidor no emite CORS: lo aplica el gateway. Única excepción: Apollo Sandbox fuera de producción, cuyas
 * consultas llegan desde un dominio de Apollo. Su verificación previa se responde aquí, antes de la autenticación.
 */
export function corsDesarrollo(produccion: boolean): RequestHandler {
  return (req, res, next) => {
    const origen = req.get('Origin');
    if (produccion || !origen || !ORIGENES_APOLLO.has(origen)) {
      next();
      return;
    }
    res.setHeader('Access-Control-Allow-Origin', origen);
    res.setHeader('Vary', 'Origin');
    if (req.method === 'OPTIONS') {
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
      const pedidos = req.get('Access-Control-Request-Headers');
      if (pedidos) {
        res.setHeader('Access-Control-Allow-Headers', pedidos);
      }
      res.setHeader('Access-Control-Max-Age', '3600');
      res.status(204).end();
      return;
    }
    res.setHeader('Access-Control-Expose-Headers', 'X-Correlation-Id');
    next();
  };
}
