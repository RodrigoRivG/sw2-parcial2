import { Cantidad } from '../shared/cantidad.vo';
import { ValorDecimal } from '../shared/decimal';
import { Dinero } from '../shared/dinero.vo';
import { ErrorDominio } from '../shared/error-dominio';
import { Insumo } from '../supply/insumo.entidad';
import { stockInsuficiente } from './errores-movimiento';
import { TipoMovimiento } from './tipo-movimiento.enum';

export interface DatosRegistroMovimiento {
  id: string;
  insumo: Insumo;
  tipo: TipoMovimiento;
  cantidad: ValorDecimal;
  motivo: string;
  actor: string;
  ahora: Date;
  idSaga?: string | null;
  idLabor?: string | null;
  /** Costo de la compensación de una Saga: el de la salida original. Si falta, el vigente del insumo. */
  costoUnitario?: Dinero;
}

export interface PropiedadesMovimiento {
  id: string;
  idInsumo: string;
  tipo: TipoMovimiento;
  cantidad: Cantidad;
  stockResultante: Cantidad;
  costoUnitario: Dinero;
  motivo: string;
  actor: string;
  idSaga: string | null;
  idLabor: string | null;
  fecha: Date;
}

/** Entrada o salida de un insumo. Es inmutable: un error se corrige con un movimiento inverso. */
export class MovimientoInventario {
  private constructor(private readonly props: PropiedadesMovimiento) {}

  /**
   * Valida la cantidad en la unidad del insumo y, para una salida, que alcance el stock leído (RN-04).
   * La garantía ante operaciones simultáneas la da la persistencia; ver `conStockResultante`.
   */
  static registrar(datos: DatosRegistroMovimiento): MovimientoInventario {
    const { insumo, tipo } = datos;
    const cantidad = Cantidad.de(datos.cantidad, insumo.unidad);
    if (!cantidad.esMayorQueCero()) {
      throw ErrorDominio.reglaNegocio('CANTIDAD_INVALIDA', 'La cantidad debe ser mayor a cero.');
    }
    if (tipo === TipoMovimiento.SALIDA && !cantidad.esMenorOIgualQue(insumo.stock)) {
      throw stockInsuficiente(insumo.id, insumo.stock, cantidad);
    }
    return new MovimientoInventario({
      id: datos.id,
      idInsumo: insumo.id,
      tipo,
      cantidad,
      stockResultante:
        tipo === TipoMovimiento.ENTRADA
          ? insumo.stock.sumar(cantidad)
          : insumo.stock.restar(cantidad),
      costoUnitario: datos.costoUnitario ?? insumo.costoUnitario,
      motivo: datos.motivo.trim(),
      actor: datos.actor,
      idSaga: datos.idSaga ?? null,
      idLabor: datos.idLabor ?? null,
      fecha: datos.ahora,
    });
  }

  static reconstruir(props: PropiedadesMovimiento): MovimientoInventario {
    return new MovimientoInventario({ ...props });
  }

  /** El stock que quedó guardado, que es el que vale si otra operación cambió el insumo antes. */
  conStockResultante(stock: Cantidad): MovimientoInventario {
    return new MovimientoInventario({ ...this.props, stockResultante: stock });
  }

  get id(): string {
    return this.props.id;
  }
  get idInsumo(): string {
    return this.props.idInsumo;
  }
  get tipo(): TipoMovimiento {
    return this.props.tipo;
  }
  get cantidad(): Cantidad {
    return this.props.cantidad;
  }
  get stockResultante(): Cantidad {
    return this.props.stockResultante;
  }
  get costoUnitario(): Dinero {
    return this.props.costoUnitario;
  }
  get motivo(): string {
    return this.props.motivo;
  }
  get actor(): string {
    return this.props.actor;
  }
  get idSaga(): string | null {
    return this.props.idSaga;
  }
  get idLabor(): string | null {
    return this.props.idLabor;
  }
  get fecha(): Date {
    return this.props.fecha;
  }
}
