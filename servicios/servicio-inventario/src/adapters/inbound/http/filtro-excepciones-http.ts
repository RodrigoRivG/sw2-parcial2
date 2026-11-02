import {
  ArgumentsHost,
  BadRequestException,
  Catch,
  ExceptionFilter,
  ForbiddenException,
  Logger,
  NotFoundException,
  UnauthorizedException,
} from '@nestjs/common';
import { Response } from 'express';
import { ErrorDominio } from '../../../domain/shared/error-dominio';
import { idCorrelacionActual } from '../../contexto-correlacion';
import { ENCABEZADO_CORRELACION } from './id-correlacion.middleware';

export interface CuerpoError {
  codigo: string;
  mensaje: string;
  detalles: unknown[];
}

/** Error de validación del DTO, con un detalle por campo. */
export class ErrorValidacion extends BadRequestException {
  constructor(readonly detalles: unknown[]) {
    super();
  }
}

const ESTADO_POR_TIPO: Record<ErrorDominio['tipo'], number> = {
  NO_ENCONTRADO: 404,
  CONFLICTO: 409,
  REGLA_NEGOCIO: 422,
};

/** Traduce toda excepción al formato común `{ codigo, mensaje, detalles, idCorrelacion }`. */
@Catch()
export class FiltroExcepcionesHttp implements ExceptionFilter {
  private readonly logger = new Logger(FiltroExcepcionesHttp.name);

  catch(excepcion: unknown, host: ArgumentsHost): void {
    const respuesta = host.switchToHttp().getResponse<Response>();
    const [estado, cuerpo] = traducir(excepcion);
    if (estado >= 500) {
      this.logger.error(
        excepcion instanceof Error ? excepcion.message : String(excepcion),
        excepcion instanceof Error ? excepcion.stack : undefined,
      );
    }
    const idCorrelacion =
      idCorrelacionActual() ?? String(respuesta.getHeader(ENCABEZADO_CORRELACION) ?? '');
    respuesta.status(estado).json({ ...cuerpo, idCorrelacion });
  }
}

export function cuerpoDatosInvalidos(detalles: unknown[] = []): CuerpoError {
  return {
    codigo: 'DATOS_INVALIDOS',
    mensaje: 'Los datos enviados no son válidos.',
    detalles,
  };
}

function traducir(excepcion: unknown): [number, CuerpoError] {
  if (excepcion instanceof ErrorDominio) {
    return [
      ESTADO_POR_TIPO[excepcion.tipo],
      { codigo: excepcion.codigo, mensaje: excepcion.message, detalles: excepcion.detalles },
    ];
  }
  if (excepcion instanceof ErrorValidacion) {
    return [400, cuerpoDatosInvalidos(excepcion.detalles)];
  }
  if (excepcion instanceof BadRequestException) {
    return [400, cuerpoDatosInvalidos()];
  }
  if (excepcion instanceof UnauthorizedException) {
    return [
      401,
      { codigo: 'NO_AUTENTICADO', mensaje: 'Se requiere un token válido.', detalles: [] },
    ];
  }
  if (excepcion instanceof ForbiddenException) {
    return [
      403,
      {
        codigo: 'SIN_PERMISO',
        mensaje: 'No tiene permiso para realizar esta operación.',
        detalles: [],
      },
    ];
  }
  if (excepcion instanceof NotFoundException) {
    return [
      404,
      { codigo: 'RECURSO_NO_ENCONTRADO', mensaje: 'El recurso solicitado no existe.', detalles: [] },
    ];
  }
  return [
    500,
    {
      codigo: 'ERROR_INTERNO',
      mensaje: 'Ocurrió un error inesperado. Intente de nuevo más tarde.',
      detalles: [],
    },
  ];
}
