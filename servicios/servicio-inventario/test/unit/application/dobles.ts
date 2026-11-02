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
import { UnidadTrabajo } from '../../../src/application/ports/unidad-trabajo.puerto';
import { Insumo } from '../../../src/domain/supply/insumo.entidad';

/** Repositorio en memoria. Guarda los insumos tal cual y lleva la versión como lo hace MongoDB. */
export class RepositorioInsumoEnMemoria implements RepositorioInsumo {
  readonly insumos = new Map<string, Insumo>();
  /** Si se define, `actualizarSiVersion` simula que otra transacción ganó la carrera. */
  forzarConflicto = false;

  async guardarNuevo(insumo: Insumo): Promise<void> {
    this.insumos.set(insumo.id, insumo);
  }

  async actualizarSiVersion(insumo: Insumo, versionEsperada: number): Promise<boolean> {
    const actual = this.insumos.get(insumo.id);
    if (this.forzarConflicto || !actual || actual.version !== versionEsperada) {
      return false;
    }
    this.insumos.set(
      insumo.id,
      Insumo.reconstruir({
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
        version: versionEsperada + 1,
        fechaCreacion: insumo.fechaCreacion,
        fechaActualizacion: insumo.fechaActualizacion,
      }),
    );
    return true;
  }

  async buscarPorId(id: string): Promise<Insumo | null> {
    return this.insumos.get(id) ?? null;
  }

  async listar(_filtros: FiltrosInsumos, paginacion: Paginacion): Promise<Pagina<Insumo>> {
    const items = [...this.insumos.values()];
    return { ...paginacion, items, total: items.length };
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
