import DecimalBase from 'decimal.js';

/** Decimal con precisión de sobra para cantidades y montos; el redondeo explícito es mitad hacia arriba. */
export const Decimal = DecimalBase.clone({ precision: 40, rounding: DecimalBase.ROUND_HALF_UP });
export type Decimal = InstanceType<typeof Decimal>;

export type ValorDecimal = string | Decimal;

/** Convierte a decimal; un texto que no es un número decimal devuelve null. */
export function aDecimal(valor: ValorDecimal): Decimal | null {
  if (valor instanceof Decimal) {
    return valor;
  }
  if (!/^-?\d+(\.\d+)?$/.test(valor.trim())) {
    return null;
  }
  return new Decimal(valor.trim());
}
