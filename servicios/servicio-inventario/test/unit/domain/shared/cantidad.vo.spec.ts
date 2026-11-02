import { Cantidad } from '../../../../src/domain/shared/cantidad.vo';
import { ErrorDominio } from '../../../../src/domain/shared/error-dominio';
import { UnidadMedida } from '../../../../src/domain/supply/unidad-medida.enum';

function codigoDe(accion: () => unknown): string | undefined {
  try {
    accion();
  } catch (error) {
    return (error as ErrorDominio).codigo;
  }
  return undefined;
}

describe('Cantidad', () => {
  it('acepta 0 y valores con hasta 3 decimales', () => {
    expect(Cantidad.de('0', UnidadMedida.KILOGRAMO).aTexto()).toBe('0.000');
    expect(Cantidad.de('120.5', UnidadMedida.LITRO).aTexto()).toBe('120.500');
    expect(Cantidad.de('0.001', UnidadMedida.KILOGRAMO).aTexto()).toBe('0.001');
  });

  it('rechaza negativos con el código indicado', () => {
    expect(codigoDe(() => Cantidad.de('-1', UnidadMedida.KILOGRAMO))).toBe('CANTIDAD_INVALIDA');
    expect(
      codigoDe(() => Cantidad.de('-0.5', UnidadMedida.KILOGRAMO, 'NIVEL_MINIMO_INVALIDO')),
    ).toBe('NIVEL_MINIMO_INVALIDO');
  });

  it('rechaza más de 3 decimales y textos no numéricos', () => {
    expect(codigoDe(() => Cantidad.de('1.2345', UnidadMedida.KILOGRAMO))).toBe(
      'CANTIDAD_INVALIDA',
    );
    expect(codigoDe(() => Cantidad.de('abc', UnidadMedida.KILOGRAMO))).toBe('CANTIDAD_INVALIDA');
  });

  it('con UNIDAD solo acepta enteros', () => {
    expect(Cantidad.de('12', UnidadMedida.UNIDAD).aTexto()).toBe('12.000');
    expect(Cantidad.de('12.000', UnidadMedida.UNIDAD).aTexto()).toBe('12.000');
    expect(codigoDe(() => Cantidad.de('2.5', UnidadMedida.UNIDAD))).toBe('CANTIDAD_INVALIDA');
  });

  it('opera sin errores de punto flotante', () => {
    const suma = Cantidad.de('0.1', UnidadMedida.LITRO).sumar(Cantidad.de('0.2', UnidadMedida.LITRO));
    expect(suma.aTexto()).toBe('0.300');
    expect(suma.esMenorOIgualQue(Cantidad.de('0.3', UnidadMedida.LITRO))).toBe(true);
    expect(
      Cantidad.de('1', UnidadMedida.LITRO).restar(Cantidad.de('0.999', UnidadMedida.LITRO)).aTexto(),
    ).toBe('0.001');
  });

  it('distingue cero de mayor que cero', () => {
    expect(Cantidad.cero().esCero()).toBe(true);
    expect(Cantidad.cero().esMayorQueCero()).toBe(false);
    expect(Cantidad.de('0.001', UnidadMedida.LITRO).esMayorQueCero()).toBe(true);
  });
});
