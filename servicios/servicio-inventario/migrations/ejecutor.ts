import { mongo } from 'mongoose';
import { migraciones } from './index';

interface MigracionAplicada {
  _id: string;
  fecha: Date;
}

/** Aplica, en orden, las migraciones que no figuran en la colección `migraciones`. */
export async function ejecutarMigraciones(db: mongo.Db): Promise<string[]> {
  const registro = db.collection<MigracionAplicada>('migraciones');
  const aplicadas: string[] = [];
  for (const migracion of migraciones) {
    if (await registro.findOne({ _id: migracion.nombre })) {
      continue;
    }
    await migracion.subir(db);
    try {
      await registro.insertOne({ _id: migracion.nombre, fecha: new Date() });
    } catch (error) {
      // Otra instancia la registró al mismo tiempo; los índices son idempotentes.
      if ((error as { code?: number }).code !== 11000) {
        throw error;
      }
    }
    aplicadas.push(migracion.nombre);
  }
  return aplicadas;
}
