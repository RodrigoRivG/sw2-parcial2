import { Cantidad } from '../shared/cantidad.vo';
import { ErrorDominio } from '../shared/error-dominio';

export function movimientoNoEncontrado(): ErrorDominio {
  return ErrorDominio.noEncontrado(
    'MOVIMIENTO_NO_ENCONTRADO',
    'El movimiento de inventario solicitado no existe.',
  );
}

/** RN-04: la salida supera el stock disponible. `detalles` informa lo disponible y lo solicitado. */
export function stockInsuficiente(
  idInsumo: string,
  stockDisponible: Cantidad,
  cantidadSolicitada: Cantidad,
): ErrorDominio {
  return ErrorDominio.reglaNegocio(
    'STOCK_INSUFICIENTE',
    'No hay stock suficiente del insumo solicitado.',
    [
      {
        idInsumo,
        stockDisponible: stockDisponible.aTexto(),
        cantidadSolicitada: cantidadSolicitada.aTexto(),
      },
    ],
  );
}
