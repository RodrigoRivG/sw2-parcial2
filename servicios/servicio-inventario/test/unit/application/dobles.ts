import { Pagina, Paginacion } from '../../../src/application/ports/pagina';
import {
  EntradaAuditoria,
  RegistroAuditoria,
} from '../../../src/application/ports/registro-auditoria.puerto';
import { Reloj } from '../../../src/application/ports/reloj.puerto';
import {
  FiltrosInsumos,
  RepositorioInsumo,
} from '../../../src/application/ports/repositorio-insumo.puerto';
import {
  FiltrosMovimientos,
  RepositorioMovimiento,
} from '../../../src/application/ports/repositorio-movimiento.puerto';
import { UnidadTrabajo } from '../../../src/application/ports/unidad-trabajo.puerto';
import { MovimientoInventario } from '../../../src/domain/movement/movimiento-inventario.entidad';
import { TipoMovimiento } from '../../../src/domain/movement/tipo-movimiento.enum';
import { Cantidad } from '../../../src/domain/shared/cantidad.vo';
import { Insumo, PropiedadesInsumo } from '../../../src/domain/supply/insumo.entidad';

/** Repositorio en memoria. Guarda los insumos tal cual y lleva la versión como lo hace MongoDB. */
export class RepositorioInsumoEnMemoria implements RepositorioInsumo {
  readonly insumos = new Map<string, Insumo>();
  /** Si se define, `actualizarSiVersion` simula que otra transacción ganó la carrera. */
  forzarConflicto = false;

  async guardarNuevo(insumo: Insumo): Promise<void> {
    this.insumos.set(insumo.id, insumo);
  }

  /** Si se define, `aplicarMovimiento` simula que otra operación consumió el stock antes. */
  forzarCarreraPerdida = false;

  async actualizarSiVersion(insumo: Insumo, versionEsperada: number): Promise<boolean> {
    const actual = this.insumos.get(insumo.id);
    if (this.forzarConflicto || !actual || actual.version !== versionEsperada) {
      return false;
    }
    this.insumos.set(insumo.id, copiarInsumo(insumo, { version: versionEsperada + 1 }));
    return true;
  }

  async aplicarMovimiento(
    id: string,
    tipo: TipoMovimiento,
    cantidad: Cantidad,
    ahora: Date,
  ): Promise<Cantidad | null> {
    const actual = this.insumos.get(id);
    const esSalida = tipo === TipoMovimiento.SALIDA;
    if (!actual || this.forzarCarreraPerdida || (esSalida && !cantidad.esMenorOIgualQue(actual.stock))) {
      return null;
    }
    const stock = esSalida ? actual.stock.restar(cantidad) : actual.stock.sumar(cantidad);
    this.insumos.set(
      id,
      copiarInsumo(actual, { stock, tieneMovimientos: true, fechaActualizacion: ahora }),
    );
    return stock;
  }

  async buscarPorId(id: string): Promise<Insumo | null> {
    return this.insumos.get(id) ?? null;
  }

  async listar(_filtros: FiltrosInsumos, paginacion: Paginacion): Promise<Pagina<Insumo>> {
    const items = [...this.insumos.values()];
    return { ...paginacion, items, total: items.length };
  }
}

export function copiarInsumo(insumo: Insumo, cambios: Partial<PropiedadesInsumo>): Insumo {
  return Insumo.reconstruir({
    id: insumo.id,
    nombre: insumo.nombre,
    categoria: insumo.categoria,
    unidad: insumo.unidad,
    stock: insumo.stock,
    nivelMinimo: insumo.nivelMinimo,
    costoUnitario: insumo.costoUnitario,
    descripcion: insumo.descripcion,
    tieneMovimientos: insumo.tieneMovimientos,
    fechaUltimaAlerta: insumo.fechaUltimaAlerta,
    version: insumo.version,
    fechaCreacion: insumo.fechaCreacion,
    fechaActualizacion: insumo.fechaActualizacion,
    ...cambios,
  });
}

export class RepositorioMovimientoEnMemoria implements RepositorioMovimiento {
  readonly movimientos: MovimientoInventario[] = [];

  async guardar(movimiento: MovimientoInventario): Promise<void> {
    this.movimientos.push(movimiento);
  }

  async buscarPorId(id: string): Promise<MovimientoInventario | null> {
    return this.movimientos.find((m) => m.id === id) ?? null;
  }

  async listar(
    _filtros: FiltrosMovimientos,
    paginacion: Paginacion,
  ): Promise<Pagina<MovimientoInventario>> {
    return { ...paginacion, items: [...this.movimientos], total: this.movimientos.length };
  }
}

export class AuditoriaEnMemoria implements RegistroAuditoria {
  readonly registros: EntradaAuditoria[] = [];

  async registrar(entrada: EntradaAuditoria): Promise<void> {
    this.registros.push(entrada);
  }
}

/** Ejecuta el trabajo sin transacción real. */
export class UnidadTrabajoDirecta implements UnidadTrabajo {
  ejecutar<T>(trabajo: () => Promise<T>): Promise<T> {
    return trabajo();
  }
}

export class RelojFijo implements Reloj {
  constructor(public instante = new Date('2026-11-02T14:00:00Z')) {}

  ahora(): Date {
    return this.instante;
  }
}
