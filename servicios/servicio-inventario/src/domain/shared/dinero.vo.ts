import { Cantidad } from './cantidad.vo';
import { Decimal, ValorDecimal, aDecimal } from './decimal';
import { ErrorDominio } from './error-dominio';

const DECIMALES_COSTO_UNITARIO = 4;

/** Monto en bolivianos (`BOB`), mayor o igual a 0. Se opera con precisión completa y se redondea solo al final. */
export class Dinero {
  private constructor(readonly valor: Decimal) {}

  /** Costo unitario: ≥ 0 y hasta 4 decimales. */
  static costoUnitario(valor: ValorDecimal): Dinero {
    const decimal = aDecimal(valor);
    if (decimal === null || decimal.decimalPlaces() > DECIMALES_COSTO_UNITARIO) {
      throw ErrorDominio.reglaNegocio(
        'COSTO_UNITARIO_INVALIDO',
        `El costo unitario admite hasta ${DECIMALES_COSTO_UNITARIO} decimales.`,
      );
    }
    if (decimal.isNegative() && !decimal.isZero()) {
      throw ErrorDominio.reglaNegocio(
        'COSTO_UNITARIO_INVALIDO',
        'El costo unitario no puede ser negativo.',
      );
    }
    return new Dinero(decimal.abs());
  }

  static cero(): Dinero {
    return new Dinero(new Decimal(0));
  }

  multiplicar(cantidad: Cantidad): Dinero {
    return new Dinero(this.valor.times(cantidad.valor));
  }

  sumar(otro: Dinero): Dinero {
    return new Dinero(this.valor.plus(otro.valor));
  }

  /** Redondeo final a 2 decimales, mitad hacia arriba. */
  redondearA2(): Dinero {
    return new Dinero(this.valor.toDecimalPlaces(2, Decimal.ROUND_HALF_UP));
  }

  aTexto(decimales: number): string {
    return this.valor.toFixed(decimales);
  }

  /** Costo unitario con escala fija de 4 decimales (`"4.8500"`). */
  aTextoCostoUnitario(): string {
    return this.aTexto(DECIMALES_COSTO_UNITARIO);
  }
}
