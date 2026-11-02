import { ConfirmChannel } from 'amqplib';

/** Colas de la Saga (README D-11, constituciones v2.6.0 de inventario y operaciones). */
export const COLA_COMANDOS = 'servicio-inventario.comandos';
export const COLA_COMANDOS_DLQ = 'servicio-inventario.comandos.dlq';
export const COLA_RESPUESTAS = 'servicio-operaciones.respuestas-saga';

/** Mensajes sin confirmar que procesa a la vez el consumidor. */
export const PREFETCH_COMANDOS = 10;

/**
 * Declara las tres colas. La de respuestas es de `servicio-operaciones`; se declara con los mismos
 * argumentos que `servicio-gestion` (durable, sin argumentos) para no perder respuestas si este
 * servicio arranca primero.
 */
export async function declararTopologiaSaga(canal: ConfirmChannel): Promise<void> {
  await canal.assertQueue(COLA_COMANDOS_DLQ, { durable: true });
  await canal.assertQueue(COLA_COMANDOS, {
    durable: true,
    arguments: {
      'x-dead-letter-exchange': '',
      'x-dead-letter-routing-key': COLA_COMANDOS_DLQ,
    },
  });
  await canal.assertQueue(COLA_RESPUESTAS, { durable: true });
  await canal.prefetch(PREFETCH_COMANDOS);
}
