import { Paginacion } from '../ports/pagina';
import {
  EstadoInventario,
  FiltrosEstadoInventario,
  RepositorioInsumo,
} from '../ports/repositorio-insumo.puerto';

/** RF-33: estado de cada insumo frente a su nivel mínimo. Solo lectura, sin auditoría. */
export class ConsultarEstadoInventarioCasoUso {
  constructor(private readonly repositorio: RepositorioInsumo) {}

  consultar(filtros: FiltrosEstadoInventario, paginacion: Paginacion): Promise<EstadoInventario> {
    return this.repositorio.consultarEstado(filtros, paginacion);
  }
}
