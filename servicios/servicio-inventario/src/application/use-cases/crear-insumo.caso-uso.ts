import { randomUUID } from 'node:crypto';
import { Cantidad } from '../../domain/shared/cantidad.vo';
import { DatosInsumo, Insumo } from '../../domain/supply/insumo.entidad';
import { RegistroAuditoria } from '../ports/registro-auditoria.puerto';
import { Reloj } from '../ports/reloj.puerto';
import { RepositorioInsumo } from '../ports/repositorio-insumo.puerto';
import { UnidadTrabajo } from '../ports/unidad-trabajo.puerto';

export interface EntradaCrearInsumo extends DatosInsumo {
  stockInicial?: string;
}

export class CrearInsumoCasoUso {
  constructor(
    private readonly repositorio: RepositorioInsumo,
    private readonly unidadTrabajo: UnidadTrabajo,
    private readonly auditoria: RegistroAuditoria,
    private readonly reloj: Reloj,
  ) {}

  ejecutar(entrada: EntradaCrearInsumo, actor: string): Promise<Insumo> {
    return this.unidadTrabajo.ejecutar(async () => {
      const insumo = Insumo.crear(randomUUID(), entrada, this.reloj.ahora());
      const stockInicial = Cantidad.de(entrada.stockInicial ?? '0', insumo.unidad);
      await this.repositorio.guardarNuevo(insumo);
      await this.auditoria.registrar({
        actor,
        accion: 'CREAR',
        entidad: 'Insumo',
        idEntidad: insumo.id,
      });
      if (stockInicial.esMayorQueCero()) {
        // Pendiente de spec-movimientos.md (T03): el stock inicial se registra como una entrada.
        throw new Error('El registro del stock inicial todavía no está implementado.');
      }
      return insumo;
    });
  }
}
