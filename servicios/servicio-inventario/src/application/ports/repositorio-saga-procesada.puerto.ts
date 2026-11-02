import { SagaProcesada } from '../../domain/saga/saga-procesada.entidad';

export interface RepositorioSagaProcesada {
  /**
   * Dentro de la transacción: crea el documento del `idSaga` si no existe y lo escribe siempre, para que
   * dos comandos del mismo `idSaga` choquen y se procesen uno después del otro (RQ-SAG-11).
   */
  obtenerParaProcesar(idSaga: string, idLabor: string, ahora: Date): Promise<SagaProcesada>;
  guardar(saga: SagaProcesada): Promise<void>;
}
