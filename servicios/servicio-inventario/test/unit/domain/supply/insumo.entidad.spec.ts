import { Cantidad } from '../../../../src/domain/shared/cantidad.vo';
import { ErrorDominio } from '../../../../src/domain/shared/error-dominio';
import { CategoriaInsumo } from '../../../../src/domain/supply/categoria-insumo.enum';
import { DatosInsumo, Insumo } from '../../../../src/domain/supply/insumo.entidad';
import { estaEnStockBajo } from '../../../../src/domain/supply/politica-stock-bajo';
import { UnidadMedida } from '../../../../src/domain/supply/unidad-medida.enum';

const AHORA = new Date('2026-11-02T14:00:00Z');

function datos(cambios: Partial<DatosInsumo> = {}): DatosInsumo {
  return {
    nombre: '  Urea 46 %  ',
    categoria: CategoriaInsumo.FERTILIZANTE,
    unidad: UnidadMedida.KILOGRAMO,
    nivelMinimo: '50',
    costoUnitario: '4.85',
    descripcion: '  Bolsa de 50 kg ',
    ...cambios,
  };
}

function codigoDe(accion: () => unknown): string | undefined {
  try {
    accion();
  } catch (error) {
    return (error as ErrorDominio).codigo;
  }
  return undefined;
}

describe('Insumo', () => {
  it('se crea con stock 0, versión 0, sin movimientos y con textos recortados', () => {
    const insumo = Insumo.crear('id-1', datos(), AHORA);
    expect(insumo.nombre).toBe('Urea 46 %');
    expect(insumo.descripcion).toBe('Bolsa de 50 kg');
    expect(insumo.stock.aTexto()).toBe('0.000');
    expect(insumo.nivelMinimo.aTexto()).toBe('50.000');
    expect(insumo.costoUnitario.aTextoCostoUnitario()).toBe('4.8500');
    expect(insumo.version).toBe(0);
    expect(insumo.tieneMovimientos).toBe(false);
    expect(insumo.fechaUltimaAlerta).toBeNull();
    expect(insumo.fechaCreacion).toEqual(AHORA);
  });

  it('una descripción vacía queda en null', () => {
    expect(Insumo.crear('id-1', datos({ descripcion: '   ' }), AHORA).descripcion).toBeNull();
    expect(Insumo.crear('id-1', datos({ descripcion: undefined }), AHORA).descripcion).toBeNull();
  });

  it('valida nivel mínimo y costo unitario', () => {
    expect(codigoDe(() => Insumo.crear('id', datos({ nivelMinimo: '-1' }), AHORA))).toBe(
      'NIVEL_MINIMO_INVALIDO',
    );
    expect(codigoDe(() => Insumo.crear('id', datos({ costoUnitario: '-1' }), AHORA))).toBe(
      'COSTO_UNITARIO_INVALIDO',
    );
    expect(
      codigoDe(() =>
        Insumo.crear('id', datos({ unidad: UnidadMedida.UNIDAD, nivelMinimo: '2.5' }), AHORA),
      ),
    ).toBe('CANTIDAD_INVALIDA');
    expect(Insumo.crear('id', datos({ costoUnitario: '0' }), AHORA).costoUnitario.aTexto(2)).toBe(
      '0.00',
    );
  });

  it('cambia la unidad si no tiene movimientos', () => {
    const insumo = Insumo.crear('id', datos(), AHORA);
    const despues = new Date('2026-11-03T10:00:00Z');
    insumo.actualizar(datos({ unidad: UnidadMedida.LITRO, costoUnitario: '5.10' }), despues);
    expect(insumo.unidad).toBe(UnidadMedida.LITRO);
    expect(insumo.costoUnitario.aTextoCostoUnitario()).toBe('5.1000');
    expect(insumo.fechaActualizacion).toEqual(despues);
    expect(insumo.fechaCreacion).toEqual(AHORA);
  });

  it('no cambia la unidad si ya tiene movimientos, pero sí los demás datos', () => {
    const insumo = Insumo.reconstruir({
      id: 'id',
      nombre: 'Urea',
      categoria: CategoriaInsumo.FERTILIZANTE,
      unidad: UnidadMedida.KILOGRAMO,
      stock: Cantidad.de('100', UnidadMedida.KILOGRAMO),
      nivelMinimo: Cantidad.de('50', UnidadMedida.KILOGRAMO),
      costoUnitario: Insumo.crear('x', datos(), AHORA).costoUnitario,
      descripcion: null,
      tieneMovimientos: true,
      fechaUltimaAlerta: null,
      version: 3,
      fechaCreacion: AHORA,
      fechaActualizacion: AHORA,
    });
    expect(codigoDe(() => insumo.actualizar(datos({ unidad: UnidadMedida.LITRO }), AHORA))).toBe(
      'UNIDAD_NO_MODIFICABLE',
    );
    insumo.actualizar(datos({ nombre: 'Urea granulada' }), AHORA);
    expect(insumo.nombre).toBe('Urea granulada');
    expect(insumo.stock.aTexto()).toBe('100.000');
    expect(insumo.version).toBe(3);
  });

  it('cambiar la unidad a UNIDAD con un nivel mínimo decimal se rechaza', () => {
    const insumo = Insumo.crear('id', datos({ nivelMinimo: '2.5' }), AHORA);
    expect(
      codigoDe(() =>
        insumo.actualizar(datos({ unidad: UnidadMedida.UNIDAD, nivelMinimo: '2.5' }), AHORA),
      ),
    ).toBe('CANTIDAD_INVALIDA');
  });
});

describe('Política de stock bajo', () => {
  const kg = (valor: string) => Cantidad.de(valor, UnidadMedida.KILOGRAMO);

  it('stock menor, igual o mayor al mínimo', () => {
    expect(estaEnStockBajo(kg('40'), kg('50'))).toBe(true);
    expect(estaEnStockBajo(kg('50'), kg('50'))).toBe(true);
    expect(estaEnStockBajo(kg('50.001'), kg('50'))).toBe(false);
  });

  it('con mínimo 0, solo el stock 0 está en stock bajo', () => {
    expect(estaEnStockBajo(kg('0'), kg('0'))).toBe(true);
    expect(estaEnStockBajo(kg('0.001'), kg('0'))).toBe(false);
  });

  it('un insumo nuevo con mínimo mayor a 0 está en stock bajo', () => {
    expect(Insumo.crear('id', datos(), AHORA).stockBajo).toBe(true);
  });
});
