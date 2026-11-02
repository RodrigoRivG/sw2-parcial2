import { AsyncLocalStorage } from 'node:async_hooks';

/** `idCorrelacion` de la solicitud o mensaje en curso, para logs, auditoría y respuestas de error. */
export const contextoCorrelacion = new AsyncLocalStorage<{ idCorrelacion: string }>();

export function idCorrelacionActual(): string | undefined {
  return contextoCorrelacion.getStore()?.idCorrelacion;
}
