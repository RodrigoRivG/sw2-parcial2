import { randomUUID } from 'node:crypto';
import { NextFunction, Request, Response } from 'express';
import { contextoCorrelacion } from '../../contexto-correlacion';

export const ENCABEZADO_CORRELACION = 'X-Correlation-Id';

/** Toma el `X-Correlation-Id` recibido del Gateway o genera uno nuevo. */
export function obtenerIdCorrelacion(solicitud: Request): string {
  const recibido = solicitud.header(ENCABEZADO_CORRELACION)?.trim();
  // Solo se acepta un identificador simple, para que no se pueda inyectar texto en los logs.
  return recibido && /^[\w-]{1,64}$/.test(recibido) ? recibido : randomUUID();
}

export function middlewareIdCorrelacion(
  solicitud: Request,
  respuesta: Response,
  siguiente: NextFunction,
): void {
  const idCorrelacion = obtenerIdCorrelacion(solicitud);
  respuesta.setHeader(ENCABEZADO_CORRELACION, idCorrelacion);
  contextoCorrelacion.run({ idCorrelacion }, siguiente);
}
