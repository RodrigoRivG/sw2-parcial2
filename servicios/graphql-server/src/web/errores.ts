import type { GraphQLFormattedError } from 'graphql';
import { GraphQLError } from 'graphql';
import { unwrapResolverError } from '@apollo/server/errors';
import type { Response } from 'express';
import { logger } from './logger';

/** Errores HTTP (formato común de los microservicios, spec-consultas.md 1.4). */
export const ERRORES_HTTP = {
  NO_AUTENTICADO: { estado: 401, mensaje: 'Debe iniciar sesión para continuar.' },
  SIN_PERMISO: { estado: 403, mensaje: 'No tiene permiso para realizar esta operación.' },
  DATOS_INVALIDOS: { estado: 400, mensaje: 'La solicitud no es válida.' },
  AUTENTICACION_NO_DISPONIBLE: {
    estado: 503,
    mensaje: 'No se pudo verificar la sesión. Intente nuevamente en unos minutos.',
  },
  ERROR_INTERNO: { estado: 500, mensaje: 'Ocurrió un error inesperado.' },
} as const;

export type CodigoHttp = keyof typeof ERRORES_HTTP;

export function responderError(res: Response, codigo: CodigoHttp): void {
  const { estado, mensaje } = ERRORES_HTTP[codigo];
  res.status(estado).json({ codigo, mensaje, detalles: [], idCorrelacion: res.locals.idCorrelacion });
}

/** Errores de campo (`extensions.codigo`). */
export const MENSAJES_CAMPO = {
  SIN_PERMISO: 'No tiene permiso para ver esta información.',
  DATOS_INVALIDOS: 'La consulta tiene datos inválidos.',
  DEPENDENCIA_NO_DISPONIBLE: 'No se pudieron obtener estos datos en este momento.',
  CONSULTA_DEMASIADO_COMPLEJA: 'La consulta pide demasiados datos a la vez.',
  ERROR_INTERNO: 'Ocurrió un error inesperado.',
} as const;

export type CodigoCampo = keyof typeof MENSAJES_CAMPO;

export class ErrorCampo extends GraphQLError {
  constructor(
    readonly codigo: CodigoCampo,
    readonly detalles: unknown[] = [],
  ) {
    super(MENSAJES_CAMPO[codigo], { extensions: { codigo, detalles } });
  }
}

/** Motivo con el que se aborta la señal del plazo de la consulta (2.6). */
export class PlazoConsultaVencido extends Error {
  constructor() {
    super('Venció el plazo de la consulta');
    this.name = 'PlazoConsultaVencido';
  }
}

const CODIGOS_ENTRADA_INVALIDA = new Set([
  'GRAPHQL_PARSE_FAILED',
  'GRAPHQL_VALIDATION_FAILED',
  'BAD_USER_INPUT',
  'BAD_REQUEST',
  'OPERATION_RESOLUTION_FAILURE',
]);

/** `formatError` de Apollo (2.7): nunca expone trazas ni mensajes internos. */
export function formatearError(formateado: GraphQLFormattedError, error: unknown): GraphQLFormattedError {
  const original = unwrapResolverError(error);
  const base = { message: '', locations: formateado.locations, path: formateado.path };
  if (original instanceof ErrorCampo) {
    return { ...base, message: original.message, extensions: { codigo: original.codigo, detalles: original.detalles } };
  }
  const codigoApollo = formateado.extensions?.code;
  if (typeof codigoApollo === 'string' && CODIGOS_ENTRADA_INVALIDA.has(codigoApollo)) {
    return {
      ...base,
      message: MENSAJES_CAMPO.DATOS_INVALIDOS,
      extensions: { codigo: 'DATOS_INVALIDOS', detalles: [formateado.message] },
    };
  }
  logger.error('Error inesperado al resolver la consulta', {
    error: original instanceof Error ? original.message : String(original),
  });
  return { ...base, message: MENSAJES_CAMPO.ERROR_INTERNO, extensions: { codigo: 'ERROR_INTERNO', detalles: [] } };
}
