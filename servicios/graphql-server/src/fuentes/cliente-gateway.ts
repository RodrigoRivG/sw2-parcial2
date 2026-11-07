import type { Configuracion } from '../config';
import type { Estadisticas } from '../web/correlacion';
import { ErrorCampo, PlazoConsultaVencido } from '../web/errores';
import { logger } from '../web/logger';
import { TokenNoDisponible, type TokenServicio } from './token-servicio';

/** Lo que el cliente necesita de la consulta en curso. */
export interface ContextoLlamada {
  idCorrelacion: string;
  senalPlazo: AbortSignal;
  estadisticas: Estadisticas;
}

export type Parametros = Record<string, string | number | boolean | null | undefined>;

/** Solo GET contra el API Gateway, con la cuenta de servicio (constitución §6, spec-consultas.md 2.6). */
export class ClienteGateway {
  constructor(
    private readonly configuracion: Configuracion,
    private readonly token: TokenServicio,
  ) {}

  /** Con `porId`, un 404 del servicio significa "no existe" y devuelve `null`. */
  async get<T>(contexto: ContextoLlamada, ruta: string, parametros: Parametros = {}, porId = false): Promise<T | null> {
    for (let intento = 0; ; intento++) {
      if (contexto.senalPlazo.aborted) {
        throw this.dependencia(contexto, ruta, 0, 'PLAZO_CONSULTA');
      }
      if (contexto.estadisticas.llamadas >= this.configuracion.maximoLlamadas) {
        throw new ErrorCampo('CONSULTA_DEMASIADO_COMPLEJA');
      }
      contexto.estadisticas.llamadas++;
      const inicio = Date.now();
      try {
        const token = await this.token.obtener(contexto.senalPlazo);
        const respuesta = await fetch(this.url(ruta, parametros), {
          headers: { Authorization: `Bearer ${token}`, 'X-Correlation-Id': contexto.idCorrelacion },
          signal: AbortSignal.any([AbortSignal.timeout(this.configuracion.tiempoLimiteLlamadaMs), contexto.senalPlazo]),
        });
        if (respuesta.status === 401 && intento === 0) {
          this.token.invalidar();
          await respuesta.body?.cancel();
          continue;
        }
        // La lectura del cuerpo usa la misma señal: un corte también puede ocurrir aquí.
        const cuerpo = await leerJson(respuesta);
        if (respuesta.ok) {
          return cuerpo as T;
        }
        if (respuesta.status === 404 && porId) {
          return null;
        }
        throw this.traducirEstado(contexto, ruta, respuesta.status, cuerpo, Date.now() - inicio);
      } catch (error) {
        if (error instanceof ErrorCampo) {
          throw error;
        }
        throw this.traducirFalla(contexto, ruta, error, Date.now() - inicio);
      }
    }
  }

  private url(ruta: string, parametros: Parametros): string {
    const consulta = new URLSearchParams();
    for (const [nombre, valor] of Object.entries(parametros)) {
      if (valor !== undefined && valor !== null) {
        consulta.set(nombre, String(valor));
      }
    }
    const texto = consulta.toString();
    return `${this.configuracion.apiGatewayUrl}${ruta}${texto ? `?${texto}` : ''}`;
  }

  private traducirEstado(contexto: ContextoLlamada, ruta: string, estado: number, cuerpo: unknown, duracionMs: number) {
    const campos = { idCorrelacion: contexto.idCorrelacion, servicio: servicio(ruta), ruta, estado, duracionMs };
    if (estado === 400) {
      const detalles = (cuerpo as { detalles?: unknown[] } | null)?.detalles;
      return new ErrorCampo('DATOS_INVALIDOS', Array.isArray(detalles) ? detalles : []);
    }
    if (estado === 503 || estado === 504) {
      logger.warn('Servicio no disponible', campos);
      return new ErrorCampo('DEPENDENCIA_NO_DISPONIBLE');
    }
    if (estado === 401) {
      logger.warn('El servicio rechazó el token de servicio renovado', campos);
      return new ErrorCampo('DEPENDENCIA_NO_DISPONIBLE');
    }
    if (estado === 403) {
      logger.error('Permiso faltante en el realm para la cuenta de servicio', campos);
    } else {
      logger.error('Respuesta inesperada de un servicio', campos);
    }
    return new ErrorCampo('ERROR_INTERNO');
  }

  private traducirFalla(contexto: ContextoLlamada, ruta: string, error: unknown, duracionMs: number) {
    if (error instanceof PlazoConsultaVencido) {
      return this.dependencia(contexto, ruta, duracionMs, 'PLAZO_CONSULTA');
    }
    if (error instanceof DOMException && error.name === 'TimeoutError') {
      return this.dependencia(contexto, ruta, duracionMs, 'TIEMPO_LIMITE_LLAMADA');
    }
    if (error instanceof TokenNoDisponible) {
      return this.dependencia(contexto, ruta, duracionMs, 'TOKEN_SERVICIO');
    }
    if (error instanceof TypeError) {
      return this.dependencia(contexto, ruta, duracionMs, 'CONEXION');
    }
    logger.error('Falla inesperada al llamar a un servicio', {
      idCorrelacion: contexto.idCorrelacion,
      servicio: servicio(ruta),
      ruta,
      error: String(error),
    });
    return new ErrorCampo('ERROR_INTERNO');
  }

  private dependencia(contexto: ContextoLlamada, ruta: string, duracionMs: number, causa: string): ErrorCampo {
    logger.warn('Llamada a un servicio cortada', {
      idCorrelacion: contexto.idCorrelacion,
      servicio: servicio(ruta),
      ruta,
      duracionMs,
      causa,
    });
    return new ErrorCampo('DEPENDENCIA_NO_DISPONIBLE');
  }
}

async function leerJson(respuesta: Response): Promise<unknown> {
  const texto = await respuesta.text();
  if (!texto) {
    return null;
  }
  try {
    return JSON.parse(texto);
  } catch {
    return null;
  }
}

/** `/api/gestion/v1/...` → `servicio-gestion`, para el log. */
function servicio(ruta: string): string {
  return `servicio-${ruta.split('/')[2] ?? 'desconocido'}`;
}
