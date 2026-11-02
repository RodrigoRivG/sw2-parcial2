import { Cantidad } from '../shared/cantidad.vo';

/** RN-05: un insumo está en stock bajo cuando su stock llega o baja de su nivel mínimo. */
export function estaEnStockBajo(stock: Cantidad, nivelMinimo: Cantidad): boolean {
  return stock.esMenorOIgualQue(nivelMinimo);
}
