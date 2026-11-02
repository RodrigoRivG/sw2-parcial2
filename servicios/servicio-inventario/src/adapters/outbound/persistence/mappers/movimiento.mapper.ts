import { MovimientoInventario } from '../../../../domain/movement/movimiento-inventario.entidad';
import { TipoMovimiento } from '../../../../domain/movement/tipo-movimiento.enum';
import { Cantidad } from '../../../../domain/shared/cantidad.vo';
import { Dinero } from '../../../../domain/shared/dinero.vo';
import { DocumentoMovimiento } from '../schemas/movimiento-inventario.esquema';
import { aDecimal128 } from './insumo.mapper';

export function aDocumento(movimiento: MovimientoInventario): DocumentoMovimiento {
  return {
    _id: movimiento.id,
    id_insumo: movimiento.idInsumo,
    tipo: movimiento.tipo,
    cantidad: aDecimal128(movimiento.cantidad.valor.toString()),
    stock_resultante: aDecimal128(movimiento.stockResultante.valor.toString()),
    costo_unitario: aDecimal128(movimiento.costoUnitario.valor.toString()),
    motivo: movimiento.motivo,
    actor: movimiento.actor,
    // Los movimientos manuales no guardan estos campos (índice parcial de id_saga).
    ...(movimiento.idSaga ? { id_saga: movimiento.idSaga } : {}),
    ...(movimiento.idLabor ? { id_labor: movimiento.idLabor } : {}),
    fecha: movimiento.fecha,
  };
}

export function aDominio(documento: DocumentoMovimiento): MovimientoInventario {
  return MovimientoInventario.reconstruir({
    id: documento._id,
    idInsumo: documento.id_insumo,
    tipo: documento.tipo as TipoMovimiento,
    cantidad: Cantidad.desdeAlmacen(documento.cantidad.toString()),
    stockResultante: Cantidad.desdeAlmacen(documento.stock_resultante.toString()),
    costoUnitario: Dinero.desdeAlmacen(documento.costo_unitario.toString()),
    motivo: documento.motivo,
    actor: documento.actor,
    idSaga: documento.id_saga ?? null,
    idLabor: documento.id_labor ?? null,
    fecha: documento.fecha,
  });
}
