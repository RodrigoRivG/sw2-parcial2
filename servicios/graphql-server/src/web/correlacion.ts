import { randomUUID } from 'node:crypto';
import type { RequestHandler } from 'express';
import { PlazoConsultaVencido } from './errores';

export const HEADER_CORRELACION = 'X-Correlation-Id';
export const RUTA_GRAPHQL = '/api/graphql';
const FORMATO_VALIDO = /^[A-Za-z0-9-]{1,64}$/;

/** Estadísticas de la consulta que el log de acceso escribe al final (2.8). */
export interface Estadisticas {
  operacion: string;
  llamadas: number;
  errores: number;
}

/**
 * Primer middleware (2.8): conserva o genera el X-Correlation-Id y, en /api/graphql, inicia el plazo de la
 * consulta al recibir la solicitud (2.6). El temporizador se limpia cuando la respuesta se cierra, también si la
 * autenticación responde antes de llegar a Apollo.
 */
export function correlacion(plazoConsultaMs: number): RequestHandler {
  return (req, res, next) => {
    const recibido = req.get(HEADER_CORRELACION);
    const idCorrelacion = recibido && FORMATO_VALIDO.test(recibido) ? recibido : randomUUID();
    res.locals.idCorrelacion = idCorrelacion;
    res.locals.inicio = Date.now();
    res.locals.estadisticas = { operacion: 'ninguna', llamadas: 0, errores: 0 } satisfies Estadisticas;
    res.setHeader(HEADER_CORRELACION, idCorrelacion);

    if (req.path === RUTA_GRAPHQL) {
      const controlador = new AbortController();
      const temporizador = setTimeout(() => controlador.abort(new PlazoConsultaVencido()), plazoConsultaMs);
      temporizador.unref();
      res.on('close', () => clearTimeout(temporizador));
      res.locals.senalPlazo = controlador.signal;
    }
    next();
  };
}
