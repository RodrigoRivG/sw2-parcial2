import type { Migracion } from './index';

/**
 * Sin índices extra (`_id` = `idSaga`). Se crea por adelantado para que el primer comando de la Saga
 * no la cree implícitamente dentro de una transacción, junto con otros comandos simultáneos.
 */
export const crearColeccionSagas: Migracion = {
  nombre: '004-crear-coleccion-sagas',
  async subir(db) {
    const existentes = await db.listCollections({ name: 'sagas_procesadas' }).toArray();
    if (existentes.length === 0) {
      await db.createCollection('sagas_procesadas');
    }
  },
};
