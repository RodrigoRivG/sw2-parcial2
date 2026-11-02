import { MovimientoInventario } from '../../domain/movement/movimiento-inventario.entidad';
import { TipoMovimiento } from '../../domain/movement/tipo-movimiento.enum';
import { Pagina, Paginacion } from './pagina';

export interface FiltrosMovimientos {
  idInsumo?: string;
  tipo?: TipoMovimiento;
  idSaga?: string;
  desde?: Date;
  hasta?: Date;
}

export interface RepositorioMovimiento {
  guardar(movimiento: MovimientoInventario): Promise<void>;
  buscarPorId(id: string): Promise<MovimientoInventario | null>;
  /** Ordenados por fecha descendente. */
  listar(
    filtros: FiltrosMovimientos,
    paginacion: Paginacion,
  ): Promise<Pagina<MovimientoInventario>>;
}
