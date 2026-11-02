import { CategoriaInsumo } from '../../domain/supply/categoria-insumo.enum';
import { Insumo } from '../../domain/supply/insumo.entidad';
import { Pagina, Paginacion } from './pagina';

export interface FiltrosInsumos {
  nombre?: string;
  categoria?: CategoriaInsumo;
  soloConStock?: boolean;
}

export interface RepositorioInsumo {
  /** Lanza `NOMBRE_INSUMO_DUPLICADO` si el nombre ya existe. */
  guardarNuevo(insumo: Insumo): Promise<void>;
  /**
   * Guarda los datos editables solo si la versión guardada es `versionEsperada`, e incrementa la versión.
   * Devuelve false si la versión no coincide. Lanza `NOMBRE_INSUMO_DUPLICADO` si el nombre ya existe.
   */
  actualizarSiVersion(insumo: Insumo, versionEsperada: number): Promise<boolean>;
  buscarPorId(id: string): Promise<Insumo | null>;
  listar(filtros: FiltrosInsumos, paginacion: Paginacion): Promise<Pagina<Insumo>>;
}
