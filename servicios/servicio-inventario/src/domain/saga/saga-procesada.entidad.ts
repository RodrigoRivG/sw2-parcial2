import { Cantidad } from '../shared/cantidad.vo';
import { Dinero } from '../shared/dinero.vo';
import { ResultadoSagaProcesada } from './resultado-saga-procesada.enum';

export type CodigoRechazoSaga =
  | 'DATOS_INVALIDOS'
  | 'INSUMO_NO_ENCONTRADO'
  | 'STOCK_INSUFICIENTE'
  | 'SAGA_COMPENSADA';

export interface ItemDescontado {
  idInsumo: string;
  cantidad: Cantidad;
  costoUnitario: Dinero;
}

/** Insumo que motivó un rechazo. `stockDisponible` es null si el insumo no existe. */
export interface InsumoAfectado {
  idInsumo: string;
  cantidadSolicitada: string;
  stockDisponible: string | null;
}

export type RespuestaDescuento =
  | { tipo: 'InsumosDescontados'; costoTotal: Dinero; items: ItemDescontado[] }
  | {
      tipo: 'InsumosRechazados';
      codigo: CodigoRechazoSaga;
      motivo: string;
      insumosAfectados: InsumoAfectado[];
    };

export interface ItemRestaurado {
  idInsumo: string;
  cantidad: Cantidad;
}

export interface RespuestaRestauracion {
  sinEfecto: boolean;
  items: ItemRestaurado[];
}

export type DecisionDescuento = 'PROCESAR' | 'REPETIR' | 'RECHAZAR_COMPENSADA';
export type DecisionRestauracion = 'RESTAURAR' | 'REPETIR' | 'SIN_EFECTO';

export interface PropiedadesSagaProcesada {
  idSaga: string;
  idLabor: string;
  /** null: el `idSaga` todavía no se procesó. */
  resultado: ResultadoSagaProcesada | null;
  /** La respuesta del primer descuento, para repetirla igual (constitución §4). */
  descuento: RespuestaDescuento | null;
  /** La respuesta de la primera restauración. */
  restauracion: RespuestaRestauracion | null;
  fechaProcesamiento: Date;
  fechaActualizacion: Date;
}

/** Estado de un `idSaga` en este servicio: idempotencia y orden entre descuento y compensación. */
export class SagaProcesada {
  private constructor(private props: PropiedadesSagaProcesada) {}

  static nueva(idSaga: string, idLabor: string, ahora: Date): SagaProcesada {
    return new SagaProcesada({
      idSaga,
      idLabor,
      resultado: null,
      descuento: null,
      restauracion: null,
      fechaProcesamiento: ahora,
      fechaActualizacion: ahora,
    });
  }

  static reconstruir(props: PropiedadesSagaProcesada): SagaProcesada {
    return new SagaProcesada({ ...props });
  }

  /** RQ-SAG-05. */
  decidirDescuento(): DecisionDescuento {
    if (this.props.descuento !== null) {
      return 'REPETIR';
    }
    if (this.props.resultado === ResultadoSagaProcesada.RESTAURADO) {
      return 'RECHAZAR_COMPENSADA';
    }
    return 'PROCESAR';
  }

  /** RQ-SAG-07. */
  decidirRestauracion(): DecisionRestauracion {
    if (this.props.restauracion !== null) {
      return 'REPETIR';
    }
    return this.props.resultado === ResultadoSagaProcesada.DESCONTADO ? 'RESTAURAR' : 'SIN_EFECTO';
  }

  registrarDescuento(respuesta: RespuestaDescuento, ahora: Date): void {
    this.props = {
      ...this.props,
      descuento: respuesta,
      resultado:
        respuesta.tipo === 'InsumosDescontados'
          ? ResultadoSagaProcesada.DESCONTADO
          : ResultadoSagaProcesada.RECHAZADO,
      fechaActualizacion: ahora,
    };
  }

  /** Un `idSaga` rechazado conserva `RECHAZADO`; el que descontó o nunca llegó queda `RESTAURADO`. */
  registrarRestauracion(respuesta: RespuestaRestauracion, ahora: Date): void {
    this.props = {
      ...this.props,
      restauracion: respuesta,
      resultado:
        this.props.resultado === ResultadoSagaProcesada.RECHAZADO
          ? ResultadoSagaProcesada.RECHAZADO
          : ResultadoSagaProcesada.RESTAURADO,
      fechaActualizacion: ahora,
    };
  }

  get idSaga(): string {
    return this.props.idSaga;
  }
  get idLabor(): string {
    return this.props.idLabor;
  }
  get resultado(): ResultadoSagaProcesada | null {
    return this.props.resultado;
  }
  get descuento(): RespuestaDescuento | null {
    return this.props.descuento;
  }
  get restauracion(): RespuestaRestauracion | null {
    return this.props.restauracion;
  }
  get fechaProcesamiento(): Date {
    return this.props.fechaProcesamiento;
  }
  get fechaActualizacion(): Date {
    return this.props.fechaActualizacion;
  }
}
