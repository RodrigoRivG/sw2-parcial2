import { MovimientoInventario } from '../../../../src/domain/movement/movimiento-inventario.entidad';
import { TipoMovimiento } from '../../../../src/domain/movement/tipo-movimiento.enum';
import { Cantidad } from '../../../../src/domain/shared/cantidad.vo';
import { Dinero } from '../../../../src/domain/shared/dinero.vo';
import { ErrorDominio } from '../../../../src/domain/shared/error-dominio';
import { CategoriaInsumo } from '../../../../src/domain/supply/categoria-insumo.enum';
import { Insumo } from '../../../../src/domain/supply/insumo.entidad';
import { UnidadMedida } from '../../../../src/domain/supply/unidad-medida.enum';

const AHORA = new Date('2026-11-02T14:00:00Z');

function insumoCon(stock: string, unidad = UnidadMedida.KILOGRAMO): Insumo {
  return Insumo.reconstruir({
    id: 'urea',
    nombre: 'Urea',
    categoria: CategoriaInsumo.FERTILIZANTE,
    unidad,
    stock: Cantidad.de(stock, unidad),
    nivelMinimo: Cantidad.de('50', unidad),
    costoUnitario: Dinero.costoUnitario('4.85'),
    descripcion: null,
    tieneMovimientos: true,
    fechaUltimaAlerta: null,
    reservaAlertaHasta: null,
    version: 0,
    fechaCreacion: AHORA,
    fechaActualizacion: AHORA,
  });
}

function registrar(insumo: Insumo, tipo: TipoMovimiento, cantidad: string, extra = {}) {
  return MovimientoInventario.registrar({
    id: 'm-1',
    insumo,
    tipo,
    cantidad,
    motivo: '  Compra  ',
    actor: 'admin-1',
    ahora: AHORA,
    ...extra,
  });
}

function errorDe(accion: () => unknown): ErrorDominio {
  try {
    accion();
  } catch (error) {
    return error as ErrorDominio;
  }
  throw new Error('Se esperaba un error de dominio');
}

describe('MovimientoInventario', () => {
  it('una entrada suma al stock y copia el costo unitario vigente', () => {
    const movimiento = registrar(insumoCon('120'), TipoMovimiento.ENTRADA, '80');
    expect(movimiento.stockResultante.aTexto()).toBe('200.000');
    expect(movimiento.cantidad.aTexto()).toBe('80.000');
    expect(movimiento.costoUnitario.aTextoCostoUnitario()).toBe('4.8500');
    expect(movimiento.motivo).toBe('Compra');
    expect(movimiento.idSaga).toBeNull();
    expect(movimiento.idLabor).toBeNull();
    expect(movimiento.fecha).toEqual(AHORA);
  });

  it('una salida resta; la salida igual al stock deja 0', () => {
    expect(registrar(insumoCon('200'), TipoMovimiento.SALIDA, '30').stockResultante.aTexto()).toBe(
      '170.000',
    );
    expect(registrar(insumoCon('170'), TipoMovimiento.SALIDA, '170').stockResultante.aTexto()).toBe(
      '0.000',
    );
  });

  it('una salida mayor al stock → STOCK_INSUFICIENTE con disponible y solicitado', () => {
    const error = errorDe(() => registrar(insumoCon('170'), TipoMovimiento.SALIDA, '170.001'));
    expect(error.codigo).toBe('STOCK_INSUFICIENTE');
    expect(error.tipo).toBe('REGLA_NEGOCIO');
    expect(error.detalles).toEqual([
      { idInsumo: 'urea', stockDisponible: '170.000', cantidadSolicitada: '170.001' },
    ]);
  });

  it.each(['0', '-1', '0.000'])('cantidad %s → CANTIDAD_INVALIDA', (cantidad) => {
    expect(errorDe(() => registrar(insumoCon('10'), TipoMovimiento.ENTRADA, cantidad)).codigo).toBe(
      'CANTIDAD_INVALIDA',
    );
  });

  it('con UNIDAD, una cantidad decimal → CANTIDAD_INVALIDA', () => {
    const insumo = insumoCon('10', UnidadMedida.UNIDAD);
    expect(errorDe(() => registrar(insumo, TipoMovimiento.ENTRADA, '2.5')).codigo).toBe(
      'CANTIDAD_INVALIDA',
    );
    expect(registrar(insumo, TipoMovimiento.ENTRADA, '2').stockResultante.aTexto()).toBe('12.000');
  });

  it('guarda los datos de la Saga y un costo unitario explícito', () => {
    const movimiento = registrar(insumoCon('10'), TipoMovimiento.ENTRADA, '5', {
      idSaga: 's-1',
      idLabor: 'l-1',
      costoUnitario: Dinero.costoUnitario('3.90'),
    });
    expect([movimiento.idSaga, movimiento.idLabor]).toEqual(['s-1', 'l-1']);
    expect(movimiento.costoUnitario.aTextoCostoUnitario()).toBe('3.9000');
  });

  it('conStockResultante devuelve una copia con el stock guardado', () => {
    const movimiento = registrar(insumoCon('10'), TipoMovimiento.ENTRADA, '5');
    const guardado = movimiento.conStockResultante(Cantidad.de('25', UnidadMedida.KILOGRAMO));
    expect(guardado.stockResultante.aTexto()).toBe('25.000');
    expect(movimiento.stockResultante.aTexto()).toBe('15.000');
    expect(guardado.id).toBe(movimiento.id);
  });
});
