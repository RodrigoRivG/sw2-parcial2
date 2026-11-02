import { randomUUID } from 'node:crypto';
import { TipoMovimiento } from '../../domain/movement/tipo-movimiento.enum';
import { Cantidad } from '../../domain/shared/cantidad.vo';
import { insumoNoEncontrado } from '../../domain/supply/errores-insumo';
import { DatosInsumo, Insumo } from '../../domain/supply/insumo.entidad';
import { RegistroAuditoria } from '../ports/registro-auditoria.puerto';
import { Reloj } from '../ports/reloj.puerto';
import { RepositorioInsumo } from '../ports/repositorio-insumo.puerto';
import { UnidadTrabajo } from '../ports/unidad-trabajo.puerto';
import { RegistrarMovimientoCasoUso } from './registrar-movimiento.caso-uso';

export interface EntradaCrearInsumo extends DatosInsumo {
  stockInicial?: string;
}

export const MOTIVO_STOCK_INICIAL = 'Stock inicial';

export class CrearInsumoCasoUso {
  constructor(
    private readonly repositorio: RepositorioInsumo,
    private readonly unidadTrabajo: UnidadTrabajo,
    private readonly auditoria: RegistroAuditoria,
    private readonly reloj: Reloj,
    private readonly registrarMovimiento: RegistrarMovimientoCasoUso,
  ) {}

  /** El stock inicial se registra como una entrada, en la misma transacción (constitución §3). */
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
      if (!stockInicial.esMayorQueCero()) {
        return insumo;
      }
      await this.registrarMovimiento.registrarDentroDeTransaccion(
        {
          idInsumo: insumo.id,
          tipo: TipoMovimiento.ENTRADA,
          cantidad: stockInicial.valor,
          motivo: MOTIVO_STOCK_INICIAL,
        },
        actor,
      );
      const conStock = await this.repositorio.buscarPorId(insumo.id);
      if (conStock === null) {
        throw insumoNoEncontrado();
      }
      return conStock;
    });
  }
}
