import type { Migracion } from './index';

export const crearIndicesMovimientos: Migracion = {
  nombre: '003-crear-indices-movimientos',
  async subir(db) {
    const movimientos = db.collection('movimientos_inventario');
    await movimientos.createIndex({ id_insumo: 1, fecha: -1 });
    await movimientos.createIndex({ fecha: -1 });
    // Solo los movimientos de la Saga tienen id_saga.
    await movimientos.createIndex(
      { id_saga: 1 },
      { partialFilterExpression: { id_saga: { $type: 'string' } } },
    );
  },
};
