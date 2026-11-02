import { movimientoNoEncontrado } from '../../domain/movement/errores-movimiento';
import { MovimientoInventario } from '../../domain/movement/movimiento-inventario.entidad';
import { Pagina, Paginacion } from '../ports/pagina';
import { FiltrosMovimientos, RepositorioMovimiento } from '../ports/repositorio-movimiento.puerto';

export class ConsultarMovimientosCasoUso {
  constructor(private readonly repositorio: RepositorioMovimiento) {}

  async obtener(id: string): Promise<MovimientoInventario> {
    const movimiento = await this.repositorio.buscarPorId(id);
    if (movimiento === null) {
      throw movimientoNoEncontrado();
    }
    return movimiento;
  }

  listar(
    filtros: FiltrosMovimientos,
    paginacion: Paginacion,
  ): Promise<Pagina<MovimientoInventario>> {
    return this.repositorio.listar(filtros, paginacion);
  }
}
