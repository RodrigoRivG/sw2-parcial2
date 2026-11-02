import amqplib, { Channel, ChannelModel } from 'amqplib';

export interface SobreRecibido {
  idMensaje: string;
  idCorrelacion: string;
  tipo: string;
  version: number;
  fechaOcurrencia: string;
  origen: string;
  datos: Record<string, unknown>;
}

/** Cola exclusiva enlazada al exchange `eventos`, como la que crea n8n (constitución §8). */
export class OyenteEventos {
  readonly recibidos: SobreRecibido[] = [];

  private constructor(
    private readonly conexion: ChannelModel,
    private readonly canal: Channel,
  ) {}

  static async escuchar(routingKey: string): Promise<OyenteEventos> {
    const url = process.env.RABBITMQ_PRUEBAS_URL;
    if (!url) {
      throw new Error('RABBITMQ_PRUEBAS_URL no está definida: falta el globalSetup de Jest.');
    }
    const conexion = await amqplib.connect(url);
    const canal = await conexion.createChannel();
    await canal.assertExchange('eventos', 'topic', { durable: true });
    const { queue } = await canal.assertQueue('', { exclusive: true, autoDelete: true });
    await canal.bindQueue(queue, 'eventos', routingKey);
    const oyente = new OyenteEventos(conexion, canal);
    await canal.consume(
      queue,
      (mensaje) => {
        if (mensaje) {
          oyente.recibidos.push(JSON.parse(mensaje.content.toString()) as SobreRecibido);
        }
      },
      { noAck: true },
    );
    return oyente;
  }

  /** Espera hasta tener `cantidad` mensajes o hasta que pase el tiempo, y devuelve lo recibido. */
  async esperar(cantidad: number, limiteMs = 5000): Promise<SobreRecibido[]> {
    const fin = Date.now() + limiteMs;
    while (this.recibidos.length < cantidad && Date.now() < fin) {
      await new Promise((resolver) => setTimeout(resolver, 50));
    }
    return [...this.recibidos];
  }

  vaciar(): void {
    this.recibidos.length = 0;
  }

  async cerrar(): Promise<void> {
    await this.canal.close();
    await this.conexion.close();
  }
}
