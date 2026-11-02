import { Cantidad } from '../shared/cantidad.vo';

/** No se publica más de una alerta por insumo en esta ventana (RN-05). */
export const VENTANA_ALERTA_MS = 24 * 60 * 60 * 1000;

/** Tiempo que dura la reserva de una alerta: si el proceso cae antes de publicar, vence y se reintenta. */
export const DURACION_RESERVA_ALERTA_MS = 60 * 1000;

/** RN-05: un insumo está en stock bajo cuando su stock llega o baja de su nivel mínimo. */
export function estaEnStockBajo(stock: Cantidad, nivelMinimo: Cantidad): boolean {
  return stock.esMenorOIgualQue(nivelMinimo);
}

export interface EstadoAlerta {
  stock: Cantidad;
  nivelMinimo: Cantidad;
  fechaUltimaAlerta: Date | null;
  reservaAlertaHasta: Date | null;
}

/**
 * Corresponde publicar la alerta si el insumo está en stock bajo, no hubo alerta en las últimas 24 h
 * y nadie la tiene reservada. Se evalúa tras cada movimiento, sin excepción por reposición.
 */
export function debeAlertar(insumo: EstadoAlerta, ahora: Date): boolean {
  if (!estaEnStockBajo(insumo.stock, insumo.nivelMinimo)) {
    return false;
  }
  const instante = ahora.getTime();
  if (
    insumo.fechaUltimaAlerta !== null &&
    instante - insumo.fechaUltimaAlerta.getTime() < VENTANA_ALERTA_MS
  ) {
    return false;
  }
  return insumo.reservaAlertaHasta === null || insumo.reservaAlertaHasta.getTime() <= instante;
}
