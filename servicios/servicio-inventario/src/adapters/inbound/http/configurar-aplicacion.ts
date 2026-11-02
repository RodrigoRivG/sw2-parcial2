import { ValidationError, ValidationPipe } from '@nestjs/common';
import { NestExpressApplication } from '@nestjs/platform-express';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { NextFunction, Request, Response, json } from 'express';
import {
  ErrorValidacion,
  FiltroExcepcionesHttp,
  cuerpoDatosInvalidos,
} from './filtro-excepciones-http';
import {
  ENCABEZADO_CORRELACION,
  middlewareIdCorrelacion,
  obtenerIdCorrelacion,
} from './id-correlacion.middleware';

export const PREFIJO_API = 'api/inventario/v1';

/**
 * Configuración HTTP común a `main.ts` y a los tests de integración.
 * La aplicación se crea con `bodyParser: false`: el JSON se lee aquí para responder
 * un cuerpo mal formado con el formato común de error.
 */
export function configurarAplicacion(app: NestExpressApplication): void {
  app.use(json({ limit: '100kb' }));
  app.use(manejarCuerpoInvalido);
  // Después del lector de JSON, para que el contexto de correlación llegue a los controladores.
  app.use(middlewareIdCorrelacion);
  app.setGlobalPrefix(PREFIJO_API, {
    exclude: ['salud', 'salud/liveness', 'salud/readiness'],
  });
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
      exceptionFactory: (errores) => new ErrorValidacion(aDetalles(errores)),
    }),
  );
  app.useGlobalFilters(new FiltroExcepcionesHttp());

  const documento = SwaggerModule.createDocument(
    app,
    new DocumentBuilder()
      .setTitle('servicio-inventario')
      .setDescription(
        'Insumos, movimientos y estado del inventario. Montos en BOB; decimales como texto.',
      )
      .setVersion('v1')
      .addBearerAuth()
      .build(),
  );
  SwaggerModule.setup('api-docs', app, documento);
}

function manejarCuerpoInvalido(
  error: { type?: string; status?: number } | undefined,
  solicitud: Request,
  respuesta: Response,
  siguiente: NextFunction,
): void {
  if (!error) {
    siguiente();
    return;
  }
  const idCorrelacion = obtenerIdCorrelacion(solicitud);
  respuesta.setHeader(ENCABEZADO_CORRELACION, idCorrelacion);
  respuesta.status(400).json({
    ...cuerpoDatosInvalidos([{ campo: 'cuerpo', mensajes: ['JSON mal formado o demasiado grande.'] }]),
    idCorrelacion,
  });
}

function aDetalles(errores: ValidationError[], prefijo = ''): unknown[] {
  return errores.flatMap((error) => {
    const campo = prefijo ? `${prefijo}.${error.property}` : error.property;
    const propios = error.constraints
      ? [{ campo, mensajes: Object.values(error.constraints) }]
      : [];
    return [...propios, ...aDetalles(error.children ?? [], campo)];
  });
}
