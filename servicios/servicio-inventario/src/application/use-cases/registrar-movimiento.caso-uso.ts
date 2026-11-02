import { randomUUID } from 'node:crypto';
import { stockInsuficiente } from '../../domain/movement/errores-movimiento';
import { MovimientoInventario } from '../../domain/movement/movimiento-inventario.entidad';
import { TipoMovimiento } from '../../domain/movement/tipo-movimiento.enum';
import { ValorDecimal } from '../../domain/shared/decimal';
import { Dinero } from '../../domain/shared/dinero.vo';
import { insumoNoEncontrado } from '../../domain/supply/errores-insumo';
import { AccionAuditoria, RegistroAuditoria } from '../ports/registro-auditoria.puerto';
import { Reloj } from '../ports/reloj.puerto';
import { RepositorioInsumo } from '../ports/repositorio-insumo.puerto';
import { RepositorioMovimiento } from '../ports/repositorio-movimiento.puerto';
import { UnidadTrabajo } from '../ports/unidad-trabajo.puerto';

export interface EntradaMovimiento {
  idInsumo: string;
  tipo: TipoMovimiento;
  cantidad: ValorDecimal;
  motivo: string;
  idSaga?: string;
  idLabor?: string;
  costoUnitario?: Dinero;
}

/**
 * Única forma de cambiar el stock (constitución §3), para los tres orígenes: stock inicial,
 * movimiento manual y Saga. El movimiento devuelto trae el `idInsumo` que, tras el commit,
 * se evalúa para la alerta de stock bajo.
 */
export class RegistrarMovimientoCasoUso {
  constructor(
    private readonly insumos: RepositorioInsumo,
    private readonly movimientos: RepositorioMovimiento,
    private readonly unidadTrabajo: UnidadTrabajo,
    private readonly auditoria: RegistroAuditoria,
    private readonly reloj: Reloj,
  ) {}

  /** Un movimiento en su propia transacción. */
  ejecutar(entrada: EntradaMovimiento, actor: string): Promise<MovimientoInventario> {
    return this.unidadTrabajo.ejecutar(() => this.registrarDentroDeTransaccion(entrada, actor));
  }

  /** Para quien ya abrió la transacción y registra varios cambios juntos. */
  async registrarDentroDeTransaccion(
    entrada: EntradaMovimiento,
    actor: string,
    accion: AccionAuditoria = 'REGISTRAR_MOVIMIENTO',
  ): Promise<MovimientoInventario> {
    const insumo = await this.insumos.buscarPorId(entrada.idInsumo);
    if (insumo === null) {
      throw insumoNoEncontrado();
    }
    const ahora = this.reloj.ahora();
    const movimiento = MovimientoInventario.registrar({
      id: randomUUID(),
      insumo,
      tipo: entrada.tipo,
      cantidad: entrada.cantidad,
      motivo: entrada.motivo,
      actor,
      ahora,
      idSaga: entrada.idSaga,
      idLabor: entrada.idLabor,
      costoUnitario: entrada.costoUnitario,
    });
    const stockNuevo = await this.insumos.aplicarMovimiento(
      insumo.id,
      movimiento.tipo,
      movimiento.cantidad,
      ahora,
    );
    if (stockNuevo === null) {
      // Otra operación consumió el stock entre la lectura y la escritura.
      throw stockInsuficiente(insumo.id, insumo.stock, movimiento.cantidad);
    }
    const guardado = movimiento.conStockResultante(stockNuevo);
    await this.movimientos.guardar(guardado);
    await this.auditoria.registrar({
      actor,
      accion,
      entidad: 'MovimientoInventario',
      idEntidad: guardado.id,
    });
    return guardado;
  }
}
