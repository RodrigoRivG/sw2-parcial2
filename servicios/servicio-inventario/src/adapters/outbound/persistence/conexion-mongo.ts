import { Inject, Injectable, OnModuleDestroy } from '@nestjs/common';
import mongoose, { Connection } from 'mongoose';
import { ejecutarMigraciones } from '../../../../migrations/ejecutor';

export const CONEXION_MONGO = 'CONEXION_MONGO';

/** Conecta a MongoDB y aplica las migraciones pendientes antes de que el servicio atienda solicitudes. */
export async function crearConexionMongo(uri: string): Promise<Connection> {
  const conexion = await mongoose
    .createConnection(uri, { autoIndex: false, autoCreate: false })
    .asPromise();
  if (!conexion.db) {
    throw new Error('No se pudo abrir la base de datos de MongoDB.');
  }
  await ejecutarMigraciones(conexion.db);
  return conexion;
}

@Injectable()
export class CierreConexionMongo implements OnModuleDestroy {
  constructor(@Inject(CONEXION_MONGO) private readonly conexion: Connection) {}

  async onModuleDestroy(): Promise<void> {
    await this.conexion.close();
  }
}
