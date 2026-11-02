import { randomUUID } from 'node:crypto';
import { AmqpConnectionManager, ChannelWrapper } from 'amqp-connection-manager';
import { ConfirmChannel } from 'amqplib';
import {
  EventoDominio,
  PublicadorEventos,
} from '../../../application/ports/publicador-eventos.puerto';
import { Reloj } from '../../../application/ports/reloj.puerto';
import { EXCHANGE_EVENTOS } from './conexion-rabbitmq';

export const ORIGEN = 'servicio-inventario';
const LIMITE_CONFIRMACION_MS = 5000;

/** Sobre común de mensajería (constitución §8). */
export interface SobreMensaje {
  idMensaje: string;
  idCorrelacion: string;
  tipo: string;
  version: number;
  fechaOcurrencia: string;
  origen: string;
  datos: Record<string, unknown>;
}

export class PublicadorEventosRabbitmq implements PublicadorEventos {
  private readonly canal: ChannelWrapper;

  constructor(
    conexion: AmqpConnectionManager,
    private readonly reloj: Reloj,
  ) {
    this.canal = conexion.createChannel({
      confirm: true,
      publishTimeout: LIMITE_CONFIRMACION_MS,
      setup: (canal: ConfirmChannel) =>
        canal.assertExchange(EXCHANGE_EVENTOS, 'topic', { durable: true }),
    });
  }

  async publicarEvento(evento: EventoDominio): Promise<void> {
    const sobre: SobreMensaje = {
      idMensaje: randomUUID(),
      idCorrelacion: evento.idCorrelacion ?? randomUUID(),
      tipo: evento.tipo,
      version: 1,
      fechaOcurrencia: this.reloj.ahora().toISOString(),
      origen: ORIGEN,
      datos: evento.datos,
    };
    // Resuelve cuando el broker confirma; si no confirma en 5 s, rechaza.
    await this.canal.publish(EXCHANGE_EVENTOS, evento.routingKey, Buffer.from(JSON.stringify(sobre)), {
      persistent: true,
      contentType: 'application/json',
      messageId: sobre.idMensaje,
      correlationId: sobre.idCorrelacion,
      type: sobre.tipo,
    });
  }
}
