import { insumoNoEncontrado } from '../../domain/supply/errores-insumo';
import { Insumo } from '../../domain/supply/insumo.entidad';
import { Pagina, Paginacion } from '../ports/pagina';
import { FiltrosInsumos, RepositorioInsumo } from '../ports/repositorio-insumo.puerto';

export class ConsultarInsumosCasoUso {
  constructor(private readonly repositorio: RepositorioInsumo) {}

  async obtener(id: string): Promise<Insumo> {
    const insumo = await this.repositorio.buscarPorId(id);
    if (insumo === null) {
      throw insumoNoEncontrado();
    }
    return insumo;
  }

  listar(filtros: FiltrosInsumos, paginacion: Paginacion): Promise<Pagina<Insumo>> {
    return this.repositorio.listar(filtros, paginacion);
  }
}
