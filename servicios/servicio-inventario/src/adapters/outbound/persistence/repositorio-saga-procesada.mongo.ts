import { Model } from 'mongoose';
import { RepositorioSagaProcesada } from '../../../application/ports/repositorio-saga-procesada.puerto';
import { SagaProcesada } from '../../../domain/saga/saga-procesada.entidad';
import { opcionesSesion } from './contexto-sesion';
import { aCamposGuardados, aDominio } from './mappers/saga-procesada.mapper';
import { DocumentoSagaProcesada } from './schemas/saga-procesada.esquema';

export class RepositorioSagaProcesadaMongo implements RepositorioSagaProcesada {
  constructor(private readonly modelo: Model<DocumentoSagaProcesada>) {}

  async obtenerParaProcesar(idSaga: string, idLabor: string, ahora: Date): Promise<SagaProcesada> {
    // Siempre escribe (fecha_actualizacion): dos transacciones del mismo idSaga producen un WriteConflict
    // y withTransaction reintenta la perdedora, que ya ve el resultado de la ganadora.
    const documento = await this.modelo
      .findOneAndUpdate(
        { _id: idSaga },
        {
          $setOnInsert: {
            id_labor: idLabor,
            resultado: null,
            descuento: null,
            restauracion: null,
            fecha_procesamiento: ahora,
          },
          $set: { fecha_actualizacion: ahora },
        },
        { ...opcionesSesion(), upsert: true, returnDocument: 'after' },
      )
      .lean<DocumentoSagaProcesada>()
      .exec();
    if (!documento) {
      throw new Error(`No se pudo leer la saga procesada ${idSaga}.`);
    }
    return aDominio(documento);
  }

  async guardar(saga: SagaProcesada): Promise<void> {
    await this.modelo.updateOne(
      { _id: saga.idSaga },
      { $set: aCamposGuardados(saga) },
      opcionesSesion(),
    );
  }
}
