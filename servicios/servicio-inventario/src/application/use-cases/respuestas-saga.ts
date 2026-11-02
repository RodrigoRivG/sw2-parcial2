import {
  RespuestaDescuento,
  RespuestaRestauracion,
} from '../../domain/saga/saga-procesada.entidad';

export type TipoRespuestaSaga = 'InsumosDescontados' | 'InsumosRechazados' | 'InsumosRestaurados';

/** Respuesta para el coordinador, con los `datos` de RQ-SAG-09 (decimales como texto). */
export interface RespuestaSaga {
  tipo: TipoRespuestaSaga;
  datos: Record<string, unknown>;
}

export interface ResultadoComandoSaga {
  respuesta: RespuestaSaga;
  /** Insumos cuyo stock cambió: se evalúa la alerta de stock bajo después de responder. */
  insumosAfectados: string[];
  /** Algo que conviene dejar en el log, como un comando repetido con otros datos. */
  advertencia?: string;
}

/** Datos del sobre común que necesitan los casos de uso. */
export interface SobreComandoSaga {
  version: unknown;
  idCorrelacion: string;
  /** Servicio que envió el comando; es el actor de la auditoría. */
  origen: string;
}

/**
 * El comando no tiene a quién responder con seguridad (por ejemplo, `RestaurarInsumos` sin un `idSaga`
 * válido). El consumidor lo envía a la Dead Letter Queue sin reintentos.
 */
export class ComandoNoProcesable extends Error {
  constructor(mensaje: string) {
    super(mensaje);
    this.name = 'ComandoNoProcesable';
  }
}

export function aRespuestaDescuento(
  idSaga: string | null,
  idLabor: string | null,
  respuesta: RespuestaDescuento,
): RespuestaSaga {
  if (respuesta.tipo === 'InsumosDescontados') {
    return {
      tipo: 'InsumosDescontados',
      datos: {
        idSaga,
        idLabor,
        costoTotal: respuesta.costoTotal.aTexto(2),
        items: respuesta.items.map((item) => ({
          idInsumo: item.idInsumo,
          cantidad: item.cantidad.aTexto(),
          costoUnitario: item.costoUnitario.aTextoCostoUnitario(),
        })),
      },
    };
  }
  return {
    tipo: 'InsumosRechazados',
    datos: {
      idSaga,
      idLabor,
      codigo: respuesta.codigo,
      motivo: respuesta.motivo,
      insumosAfectados: respuesta.insumosAfectados,
    },
  };
}

export function aRespuestaRestauracion(
  idSaga: string,
  idLabor: string,
  respuesta: RespuestaRestauracion,
): RespuestaSaga {
  return {
    tipo: 'InsumosRestaurados',
    datos: {
      idSaga,
      idLabor,
      sinEfecto: respuesta.sinEfecto,
      items: respuesta.items.map((item) => ({
        idInsumo: item.idInsumo,
        cantidad: item.cantidad.aTexto(),
      })),
    },
  };
}
