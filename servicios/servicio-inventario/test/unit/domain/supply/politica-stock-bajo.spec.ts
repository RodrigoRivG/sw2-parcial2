import { Cantidad } from '../../../../src/domain/shared/cantidad.vo';
import {
  EstadoAlerta,
  VENTANA_ALERTA_MS,
  debeAlertar,
} from '../../../../src/domain/supply/politica-stock-bajo';
import { UnidadMedida } from '../../../../src/domain/supply/unidad-medida.enum';

const AHORA = new Date('2026-11-02T10:00:00Z');
const MINUTO = 60 * 1000;
const kg = (valor: string) => Cantidad.de(valor, UnidadMedida.KILOGRAMO);

function estado(cambios: Partial<EstadoAlerta> = {}): EstadoAlerta {
  return {
    stock: kg('40'),
    nivelMinimo: kg('50'),
    fechaUltimaAlerta: null,
    reservaAlertaHasta: null,
    ...cambios,
  };
}

const antes = (milisegundos: number) => new Date(AHORA.getTime() - milisegundos);
const despues = (milisegundos: number) => new Date(AHORA.getTime() + milisegundos);

describe('debeAlertar (RN-05, regla de 24 h)', () => {
  it('stock bajo sin alerta previa → alerta', () => {
    expect(debeAlertar(estado(), AHORA)).toBe(true);
    expect(debeAlertar(estado({ stock: kg('50') }), AHORA)).toBe(true);
  });

  it('stock por encima del mínimo → no alerta', () => {
    expect(debeAlertar(estado({ stock: kg('50.001') }), AHORA)).toBe(false);
  });

  it('alerta hace 23 h 59 min → no; hace 24 h exactas o más → sí', () => {
    expect(debeAlertar(estado({ fechaUltimaAlerta: antes(VENTANA_ALERTA_MS - MINUTO) }), AHORA)).toBe(
      false,
    );
    expect(debeAlertar(estado({ fechaUltimaAlerta: antes(VENTANA_ALERTA_MS) }), AHORA)).toBe(true);
    expect(debeAlertar(estado({ fechaUltimaAlerta: antes(2 * VENTANA_ALERTA_MS) }), AHORA)).toBe(
      true,
    );
  });

  it('reserva vigente → no; reserva vencida o que vence ahora → sí', () => {
    expect(debeAlertar(estado({ reservaAlertaHasta: despues(MINUTO) }), AHORA)).toBe(false);
    expect(debeAlertar(estado({ reservaAlertaHasta: AHORA }), AHORA)).toBe(true);
    expect(debeAlertar(estado({ reservaAlertaHasta: antes(MINUTO) }), AHORA)).toBe(true);
  });
});
