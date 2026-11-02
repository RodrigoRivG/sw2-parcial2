/** Ejecuta un trabajo en una transacción: todo lo que guarda se confirma junto o no se guarda nada. */
export interface UnidadTrabajo {
  ejecutar<T>(trabajo: () => Promise<T>): Promise<T>;
}
