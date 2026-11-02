import {
  conflictoConcurrencia,
  insumoNoEncontrado,
} from '../../domain/supply/errores-insumo';
import { DatosInsumo, Insumo } from '../../domain/supply/insumo.entidad';
import { RegistroAuditoria } from '../ports/registro-auditoria.puerto';
import { Reloj } from '../ports/reloj.puerto';
import { RepositorioInsumo } from '../ports/repositorio-insumo.puerto';
import { UnidadTrabajo } from '../ports/unidad-trabajo.puerto';

export interface EntradaActualizarInsumo extends DatosInsumo {
  version: number;
}

export class ActualizarInsumoCasoUso {
  constructor(
    private readonly repositorio: RepositorioInsumo,
    private readonly unidadTrabajo: UnidadTrabajo,
    private readonly auditoria: RegistroAuditoria,
    private readonly reloj: Reloj,
  ) {}

  ejecutar(id: string, entrada: EntradaActualizarInsumo, actor: string): Promise<Insumo> {
    return this.unidadTrabajo.ejecutar(async () => {
      const insumo = await this.repositorio.buscarPorId(id);
      if (insumo === null) {
        throw insumoNoEncontrado();
      }
      if (insumo.version !== entrada.version) {
        throw conflictoConcurrencia();
      }
      insumo.actualizar(entrada, this.reloj.ahora());
      if (!(await this.repositorio.actualizarSiVersion(insumo, entrada.version))) {
        throw conflictoConcurrencia();
      }
      await this.auditoria.registrar({
        actor,
        accion: 'MODIFICAR',
        entidad: 'Insumo',
        idEntidad: id,
      });
      const actualizado = await this.repositorio.buscarPorId(id);
      if (actualizado === null) {
        throw insumoNoEncontrado();
      }
      return actualizado;
    });
  }
}
