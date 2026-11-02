import { AsyncLocalStorage } from 'node:async_hooks';
import { ClientSession } from 'mongoose';

/** Sesión de la transacción en curso. La abre `UnidadTrabajoMongo` y la usan los repositorios. */
export const contextoSesion = new AsyncLocalStorage<ClientSession>();

export function opcionesSesion(): { session?: ClientSession } {
  const session = contextoSesion.getStore();
  return session ? { session } : {};
}

export function esClaveDuplicada(error: unknown): boolean {
  return (error as { code?: number } | null)?.code === 11000;
}
