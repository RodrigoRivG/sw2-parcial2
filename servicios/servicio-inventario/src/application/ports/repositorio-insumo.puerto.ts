import { TipoMovimiento } from '../../domain/movement/tipo-movimiento.enum';
import { Cantidad } from '../../domain/shared/cantidad.vo';
import { CategoriaInsumo } from '../../domain/supply/categoria-insumo.enum';
import { Insumo } from '../../domain/supply/insumo.entidad';
import { Pagina, Paginacion } from './pagina';

export interface FiltrosInsumos {
  nombre?: string;
  categoria?: CategoriaInsumo;
  soloConStock?: boolean;
}

export interface FiltrosEstadoInventario {
  categoria?: CategoriaInsumo;
  soloStockBajo?: boolean;
}

/** RF-33: insumos con los de stock bajo primero; el resumen no depende de `soloStockBajo` ni de la página. */
export interface EstadoInventario extends Pagina<Insumo> {
  resumen: { totalInsumos: number; totalStockBajo: number };
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
  /**
   * Suma o resta la cantidad al stock de forma atómica, sin cambiar la versión del insumo.
   * Una salida solo se aplica si `stock >= cantidad`. Devuelve el stock resultante, o null si no se aplicó.
   */
  aplicarMovimiento(
    id: string,
    tipo: TipoMovimiento,
    cantidad: Cantidad,
    ahora: Date,
  ): Promise<Cantidad | null>;
  listar(filtros: FiltrosInsumos, paginacion: Paginacion): Promise<Pagina<Insumo>>;
  /**
   * Reserva la alerta de stock bajo de forma atómica: solo si `fechaUltimaAlerta` sigue siendo la leída
   * y no hay otra reserva vigente. Devuelve false si otro proceso la reservó o la publicó antes.
   */
  reservarAlerta(
    id: string,
    fechaUltimaAlertaLeida: Date | null,
    ahora: Date,
    reservaHasta: Date,
  ): Promise<boolean>;
  /** La alerta se publicó: guarda la fecha y libera la reserva. */
  confirmarAlerta(id: string, fecha: Date): Promise<void>;
  /** La publicación falló: libera la reserva sin tocar `fechaUltimaAlerta`. */
  liberarReserva(id: string): Promise<void>;
  /** Orden: stock bajo primero, luego por nombre y, para desempatar, por id. */
  consultarEstado(
    filtros: FiltrosEstadoInventario,
    paginacion: Paginacion,
  ): Promise<EstadoInventario>;
}
