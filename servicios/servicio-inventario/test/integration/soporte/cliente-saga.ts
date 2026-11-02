import { randomUUID } from 'node:crypto';
import amqplib, { Channel, ChannelModel } from 'amqplib';
import {
  COLA_COMANDOS,
  COLA_COMANDOS_DLQ,
  COLA_RESPUESTAS,
} from '../../../src/adapters/inbound/messaging/topologia-saga';
import { SobreRecibido } from './oyente-eventos';

export interface OpcionesComando {
  idCorrelacion?: string;
  idMensaje?: string;
  version?: unknown;
  origen?: string;
}

/** Hace de coordinador (`servicio-operaciones`): envía comandos y lee respuestas y la DLQ. */
export class ClienteSaga {
  readonly respuestas: SobreRecibido[] = [];

  private constructor(
    private readonly conexion: ChannelModel,
    private readonly canal: Channel,
  ) {}

  static async conectar(): Promise<ClienteSaga> {
    const url = process.env.RABBITMQ_PRUEBAS_URL;
    if (!url) {
      throw new Error('RABBITMQ_PRUEBAS_URL no está definida: falta el globalSetup de Jest.');
    }
    const conexion = await amqplib.connect(url);
    const canal = await conexion.createChannel();
    // Mismos argumentos que declara el servicio (topologia-saga.ts).
    await canal.assertQueue(COLA_COMANDOS_DLQ, { durable: true });
    await canal.assertQueue(COLA_COMANDOS, {
      durable: true,
      arguments: { 'x-dead-letter-exchange': '', 'x-dead-letter-routing-key': COLA_COMANDOS_DLQ },
    });
    await canal.assertQueue(COLA_RESPUESTAS, { durable: true });
    for (const cola of [COLA_COMANDOS_DLQ, COLA_RESPUESTAS]) {
      await canal.purgeQueue(cola);
    }
    const cliente = new ClienteSaga(conexion, canal);
    await canal.consume(
      COLA_RESPUESTAS,
      (mensaje) => {
        if (mensaje) {
          cliente.respuestas.push(JSON.parse(mensaje.content.toString()) as SobreRecibido);
        }
      },
      { noAck: true },
    );
    return cliente;
  }

  /** Publica un comando con el sobre común. `idCorrelacion` es el `idSaga` de los datos si no se indica. */
  enviar(tipo: string, datos: Record<string, unknown>, opciones: OpcionesComando = {}): string {
    const idMensaje = opciones.idMensaje ?? randomUUID();
    const sobre = {
      idMensaje,
      idCorrelacion: opciones.idCorrelacion ?? datos.idSaga,
      tipo,
      version: 'version' in opciones ? opciones.version : 1,
      fechaOcurrencia: new Date().toISOString(),
      origen: opciones.origen ?? 'servicio-operaciones',
      datos,
    };
    this.enviarCrudo(JSON.stringify(sobre));
    return idMensaje;
  }

  enviarCrudo(contenido: string): void {
    this.canal.sendToQueue(COLA_COMANDOS, Buffer.from(contenido), { persistent: true });
  }

  /** Espera hasta tener `cantidad` respuestas con ese `idCorrelacion`. */
  async esperarRespuestas(
    idCorrelacion: string,
    cantidad = 1,
    limiteMs = 10_000,
  ): Promise<SobreRecibido[]> {
    const fin = Date.now() + limiteMs;
    const propias = () => this.respuestas.filter((r) => r.idCorrelacion === idCorrelacion);
    while (propias().length < cantidad && Date.now() < fin) {
      await new Promise((resolver) => setTimeout(resolver, 25));
    }
    return propias();
  }

  async esperarRespuesta(idCorrelacion: string): Promise<SobreRecibido> {
    const [respuesta] = await this.esperarRespuestas(idCorrelacion, 1);
    if (!respuesta) {
      throw new Error(`No llegó respuesta para ${idCorrelacion}`);
    }
    return respuesta;
  }

  /** Lee (y confirma) hasta `cantidad` mensajes de la DLQ, esperando como máximo `limiteMs`. */
  async leerDlq(cantidad: number, limiteMs = 5000): Promise<string[]> {
    const leidos: string[] = [];
    const fin = Date.now() + limiteMs;
    while (leidos.length < cantidad && Date.now() < fin) {
      const mensaje = await this.canal.get(COLA_COMANDOS_DLQ, { noAck: true });
      if (mensaje) {
        leidos.push(mensaje.content.toString());
      } else {
        await new Promise((resolver) => setTimeout(resolver, 50));
      }
    }
    return leidos;
  }

  async cerrar(): Promise<void> {
    await this.canal.close();
    await this.conexion.close();
  }
}
