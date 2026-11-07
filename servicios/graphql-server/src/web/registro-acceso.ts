import type { RequestHandler } from 'express';
import type { Estadisticas } from './correlacion';
import { logger } from './logger';

/** Un log por solicitud, sin token, consulta ni variables (constitución §7). */
export const registroAcceso: RequestHandler = (req, res, next) => {
  res.on('finish', () => {
    const estadisticas = res.locals.estadisticas as Estadisticas;
    logger.info('Solicitud atendida', {
      idCorrelacion: res.locals.idCorrelacion,
      metodo: req.method,
      ruta: req.originalUrl.split('?')[0],
      operacion: estadisticas.operacion,
      estado: res.statusCode,
      duracionMs: Date.now() - (res.locals.inicio as number),
      cantidadLlamadas: estadisticas.llamadas,
      cantidadErrores: estadisticas.errores,
      sub: res.locals.usuario?.sub ?? '',
    });
  });
  next();
};
