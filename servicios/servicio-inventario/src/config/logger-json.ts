import { ConsoleLogger, LogLevel } from '@nestjs/common';
import { idCorrelacionActual } from '../adapters/contexto-correlacion';

/** Logs en JSON (RNF-22) con el `idCorrelacion` de la solicitud o mensaje en curso. */
export class LoggerJson extends ConsoleLogger {
  constructor() {
    super({ json: true });
  }

  protected getJsonLogObject(
    message: unknown,
    options: {
      context: string;
      logLevel: LogLevel;
      writeStreamType?: 'stdout' | 'stderr';
      errorStack?: unknown;
    },
  ) {
    const registro = super.getJsonLogObject(message, options);
    const idCorrelacion = idCorrelacionActual();
    return idCorrelacion ? { ...registro, idCorrelacion } : registro;
  }
}
