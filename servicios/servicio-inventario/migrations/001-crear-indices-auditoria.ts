import type { Migracion } from './index';

export const crearIndicesAuditoria: Migracion = {
  nombre: '001-crear-indices-auditoria',
  async subir(db) {
    await db.collection('registros_auditoria').createIndex({ entidad: 1, id_entidad: 1 });
  },
};
