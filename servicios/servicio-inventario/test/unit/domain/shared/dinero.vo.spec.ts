import { Cantidad } from '../../../../src/domain/shared/cantidad.vo';
import { Dinero } from '../../../../src/domain/shared/dinero.vo';
import { ErrorDominio } from '../../../../src/domain/shared/error-dominio';
import { UnidadMedida } from '../../../../src/domain/supply/unidad-medida.enum';

const kg = (valor: string) => Cantidad.de(valor, UnidadMedida.KILOGRAMO);

describe('Dinero', () => {
  it('acepta costo unitario 0 y hasta 4 decimales', () => {
    expect(Dinero.costoUnitario('0').aTextoCostoUnitario()).toBe('0.0000');
    expect(Dinero.costoUnitario('4.85').aTextoCostoUnitario()).toBe('4.8500');
    expect(Dinero.costoUnitario('0.1235').aTextoCostoUnitario()).toBe('0.1235');
  });

  it('rechaza costos negativos o con más de 4 decimales', () => {
    for (const valor of ['-1', '1.23456', 'x']) {
      expect(() => Dinero.costoUnitario(valor)).toThrow(ErrorDominio);
      try {
        Dinero.costoUnitario(valor);
      } catch (error) {
        expect((error as ErrorDominio).codigo).toBe('COSTO_UNITARIO_INVALIDO');
      }
    }
  });

  it('multiplica y suma con precisión completa', () => {
    const total = Dinero.costoUnitario('4.85')
      .multiplicar(kg('100'))
      .sumar(Dinero.costoUnitario('38.20').multiplicar(kg('2.5')));
    expect(total.aTexto(2)).toBe('580.50');
    expect(Dinero.costoUnitario('0.1235').multiplicar(kg('3')).aTexto(4)).toBe('0.3705');
  });

  it('redondea a 2 decimales mitad hacia arriba, solo al final', () => {
    expect(Dinero.costoUnitario('0.1235').multiplicar(kg('3')).redondearA2().aTexto(2)).toBe('0.37');
    expect(Dinero.costoUnitario('0.125').redondearA2().aTexto(2)).toBe('0.13');
    expect(Dinero.costoUnitario('0.124').redondearA2().aTexto(2)).toBe('0.12');
    expect(Dinero.cero().redondearA2().aTexto(2)).toBe('0.00');
  });
});
