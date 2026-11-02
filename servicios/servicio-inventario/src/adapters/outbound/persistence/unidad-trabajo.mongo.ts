import { Connection } from 'mongoose';
import { UnidadTrabajo } from '../../../application/ports/unidad-trabajo.puerto';
import { contextoSesion } from './contexto-sesion';

export class UnidadTrabajoMongo implements UnidadTrabajo {
  constructor(private readonly conexion: Connection) {}

  async ejecutar<T>(trabajo: () => Promise<T>): Promise<T> {
    // Dentro de otra unidad de trabajo se reutiliza su transacción.
    if (contextoSesion.getStore()) {
      return trabajo();
    }
    const sesion = await this.conexion.startSession();
    try {
      let resultado: T | undefined;
      // withTransaction reintenta el trabajo completo ante errores transitorios (WriteConflict).
      await sesion.withTransaction(async () => {
        resultado = await contextoSesion.run(sesion, trabajo);
      });
      return resultado as T;
    } finally {
      await sesion.endSession();
    }
  }
}
