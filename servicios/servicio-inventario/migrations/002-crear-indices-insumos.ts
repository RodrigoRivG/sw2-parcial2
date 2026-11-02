import type { Migracion } from './index';

export const crearIndicesInsumos: Migracion = {
  nombre: '002-crear-indices-insumos',
  async subir(db) {
    const insumos = db.collection('insumos');
    await insumos.createIndex(
      { nombre_normalizado: 1 },
      { unique: true, name: 'ux_insumos_nombre_normalizado' },
    );
    await insumos.createIndex({ categoria: 1, nombre_normalizado: 1 });
  },
};
