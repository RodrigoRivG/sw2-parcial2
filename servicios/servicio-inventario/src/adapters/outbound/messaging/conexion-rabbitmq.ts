import { Inject, Injectable, OnApplicationShutdown } from '@nestjs/common';
import amqp, { AmqpConnectionManager } from 'amqp-connection-manager';

export const CONEXION_RABBITMQ = 'CONEXION_RABBITMQ';

/** Exchange topic común para los eventos (constitución §8). */
export const EXCHANGE_EVENTOS = 'eventos';

/**
 * Conexión que se reconecta sola. No se espera a que conecte: si RabbitMQ está caído, el servicio
 * arranca igual y sigue registrando movimientos (RNF-08); `/salud/readiness` lo informa.
 */
export function crearConexionRabbitmq(url: string): AmqpConnectionManager {
  return amqp.connect([url], { heartbeatIntervalInSeconds: 30, reconnectTimeInSeconds: 5 });
}

@Injectable()
export class CierreConexionRabbitmq implements OnApplicationShutdown {
  constructor(@Inject(CONEXION_RABBITMQ) private readonly conexion: AmqpConnectionManager) {}

  async onApplicationShutdown(): Promise<void> {
    await this.conexion.close();
  }
}
