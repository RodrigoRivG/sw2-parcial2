import { UnidadMedida } from '../supply/unidad-medida.enum';
import { Decimal, ValorDecimal, aDecimal } from './decimal';
import { ErrorDominio } from './error-dominio';

const DECIMALES_MAXIMOS = 3;

/**
 * Cantidad de un insumo en su unidad: mayor o igual a 0, hasta 3 decimales, entera con `UNIDAD`.
 * `codigoSiNegativo` permite reutilizarla para el nivel mínimo (`NIVEL_MINIMO_INVALIDO`).
 */
export class Cantidad {
  private constructor(readonly valor: Decimal) {}

  static de(
    valor: ValorDecimal,
    unidad: UnidadMedida,
    codigoSiNegativo = 'CANTIDAD_INVALIDA',
  ): Cantidad {
    const decimal = aDecimal(valor);
    if (decimal === null || decimal.decimalPlaces() > DECIMALES_MAXIMOS) {
      throw ErrorDominio.reglaNegocio(
        'CANTIDAD_INVALIDA',
        `La cantidad admite hasta ${DECIMALES_MAXIMOS} decimales.`,
      );
    }
    if (decimal.isNegative() && !decimal.isZero()) {
      throw ErrorDominio.reglaNegocio(codigoSiNegativo, 'El valor no puede ser negativo.');
    }
    if (unidad === UnidadMedida.UNIDAD && !decimal.isInteger()) {
      throw ErrorDominio.reglaNegocio(
        'CANTIDAD_INVALIDA',
        'Con la unidad UNIDAD solo se admiten valores enteros.',
      );
    }
    return new Cantidad(decimal.abs());
  }

  static cero(): Cantidad {
    return new Cantidad(new Decimal(0));
  }

  esCero(): boolean {
    return this.valor.isZero();
  }

  esMayorQueCero(): boolean {
    return this.valor.greaterThan(0);
  }

  sumar(otra: Cantidad): Cantidad {
    return new Cantidad(this.valor.plus(otra.valor));
  }

  /** Resta sin validar el resultado: quien la usa ya comprobó que alcanza. */
  restar(otra: Cantidad): Cantidad {
    return new Cantidad(this.valor.minus(otra.valor));
  }

  esMenorOIgualQue(otra: Cantidad): boolean {
    return this.valor.lessThanOrEqualTo(otra.valor);
  }

  /** Texto con escala fija de 3 decimales (`"120.500"`). */
  aTexto(): string {
    return this.valor.toFixed(DECIMALES_MAXIMOS);
  }
}
