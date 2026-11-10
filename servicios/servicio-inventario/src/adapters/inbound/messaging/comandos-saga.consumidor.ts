import { randomUUID } from 'node:crypto';
import {
  Inject,
  Injectable,
  Logger,
  OnApplicationBootstrap,
  OnModuleDestroy,
  Optional,
} from '@nestjs/common';
import { AmqpConnectionManager, ChannelWrapper } from 'amqp-connection-manager';
import { ConfirmChannel, ConsumeMessage } from 'amqplib';
import { DescontarInsumosCasoUso } from '../../../application/use-cases/descontar-insumos.caso-uso';
import {
  ComandoNoProcesable,
  RespuestaSaga,
  ResultadoComandoSaga,
} from '../../../application/use-cases/respuestas-saga';
import { RestaurarInsumosCasoUso } from '../../../application/use-cases/restaurar-insumos.caso-uso';
import { Reloj } from '../../../application/ports/reloj.puerto';
import { CONFIGURACION, Configuracion } from '../../../config/validacion-entorno';
import { contextoCorrelacion } from '../../contexto-correlacion';
import { CONEXION_RABBITMQ } from '../../outbound/messaging/conexion-rabbitmq';
import { ORIGEN, SobreMensaje } from '../../outbound/messaging/publicador-eventos.rabbitmq';
import { RelojSistema } from '../../outbound/reloj-sistema';
import { EvaluacionStockBajo } from '../evaluacion-stock-bajo';
import { SobreComando, SobreInvalido, interpretarSobre } from './sobre-mensaje';
import { COLA_COMANDOS, COLA_RESPUESTAS, declararTopologiaSaga } from './topologia-saga';

/** Espera antes de cada reintento ante un fallo técnico: 3 reintentos y luego la DLQ (RNF-11). */
export const ESPERAS_REINTENTO_SAGA = 'ESPERAS_REINTENTO_SAGA';
export const ESPERAS_REINTENTO_POR_DEFECTO = [1000, 2000, 4000];

const LIMITE_CONFIRMACION_MS = 5000;

/**
 * Participante de la Saga (constitución §5): consume `DescontarInsumos` y `RestaurarInsumos` de
 * `servicio-inventario.comandos` y responde en la cola del coordinador. Los rechazos de negocio se
 * responden; los fallos técnicos se reintentan y, agotados, el mensaje pasa a la DLQ sin respuesta.
 */
@Injectable()
export class ComandosSagaConsumidor implements OnApplicationBootstrap, OnModuleDestroy {
  private readonly logger = new Logger(ComandosSagaConsumidor.name);
  private readonly canal: ChannelWrapper;
  private readonly enCurso = new Set<Promise<void>>();

  constructor(
    @Inject(CONEXION_RABBITMQ) conexion: AmqpConnectionManager,
    @Inject(DescontarInsumosCasoUso) private readonly descontar: DescontarInsumosCasoUso,
    @Inject(RestaurarInsumosCasoUso) private readonly restaurar: RestaurarInsumosCasoUso,
    private readonly evaluacionStockBajo: EvaluacionStockBajo,
    @Inject(RelojSistema) private readonly reloj: Reloj,
    @Inject(ESPERAS_REINTENTO_SAGA) private readonly esperas: number[],
    @Optional() @Inject(CONFIGURACION) private readonly configuracion?: Configuracion,
  ) {
    this.canal = conexion.createChannel({
      confirm: true,
      publishTimeout: LIMITE_CONFIRMACION_MS,
      setup: (canal: ConfirmChannel) => declararTopologiaSaga(canal),
    });
  }

  onApplicationBootstrap(): void {
    if (this.configuracion?.rabbitmqConsumidorActivo === false) {
      this.logger.log('Consumidor Saga desactivado en esta copia HTTP');
      return;
    }
    // No se espera: si RabbitMQ está caído, el servicio arranca igual y el consumidor se registra al conectar.
    this.canal
      .consume(COLA_COMANDOS, (mensaje) => this.recibir(mensaje), { noAck: false })
      .catch((error: unknown) =>
        this.logger.error(`No se pudo consumir ${COLA_COMANDOS}: ${String(error)}`),
      );
  }

  /** Deja de recibir, termina los comandos en curso y cierra el canal. */
  async onModuleDestroy(): Promise<void> {
    await this.canal.cancelAll().catch(() => undefined);
    await Promise.allSettled([...this.enCurso]);
    await this.canal.close();
  }

  private async recibir(mensaje: ConsumeMessage | null): Promise<void> {
    if (!mensaje) {
      return;
    }
    const trabajo = this.procesar(mensaje);
    this.enCurso.add(trabajo);
    try {
      await trabajo;
    } finally {
      this.enCurso.delete(trabajo);
    }
  }

  private async procesar(mensaje: ConsumeMessage): Promise<void> {
    let sobre: SobreComando;
    try {
      sobre = interpretarSobre(mensaje.content);
    } catch (error) {
      this.logger.error(
        `Mensaje enviado a la DLQ sin reintentos: ${error instanceof SobreInvalido ? error.message : String(error)}`,
      );
      this.canal.nack(mensaje, false, false);
      return;
    }
    await contextoCorrelacion.run({ idCorrelacion: sobre.idCorrelacion }, () =>
      this.procesarConReintentos(mensaje, sobre),
    );
  }

  private async procesarConReintentos(mensaje: ConsumeMessage, sobre: SobreComando): Promise<void> {
    const descripcion = `${sobre.tipo} (idMensaje ${sobre.idMensaje})`;
    for (let intento = 0; ; intento++) {
      try {
        const resultado = await this.ejecutar(sobre);
        if (resultado.advertencia) {
          this.logger.warn(resultado.advertencia);
        }
        await this.responder(sobre, resultado.respuesta);
        this.canal.ack(mensaje);
        this.logger.log(`${descripcion} procesado: ${resultado.respuesta.tipo}`);
        if (resultado.insumosAfectados.length > 0) {
          this.evaluacionStockBajo.programar(resultado.insumosAfectados);
        }
        return;
      } catch (error) {
        const detalle = error instanceof Error ? error.message : String(error);
        if (error instanceof ComandoNoProcesable) {
          this.logger.error(`${descripcion} enviado a la DLQ sin reintentos: ${detalle}`);
          this.canal.nack(mensaje, false, false);
          return;
        }
        if (intento >= this.esperas.length) {
          this.logger.error(
            `${descripcion} enviado a la DLQ tras ${this.esperas.length} reintentos: ${detalle}`,
          );
          this.canal.nack(mensaje, false, false);
          return;
        }
        this.logger.warn(
          `${descripcion} falló (${detalle}); reintento ${intento + 1} de ${this.esperas.length}`,
        );
        await new Promise((resolver) => setTimeout(resolver, this.esperas[intento]));
      }
    }
  }

  private ejecutar(sobre: SobreComando): Promise<ResultadoComandoSaga> {
    const datosSobre = {
      version: sobre.version,
      idCorrelacion: sobre.idCorrelacion,
      origen: sobre.origen,
    };
    return sobre.tipo === 'DescontarInsumos'
      ? this.descontar.ejecutar(sobre.datos, datosSobre)
      : this.restaurar.ejecutar(sobre.datos, datosSobre);
  }

  /** En la cola del coordinador, con el mismo `idCorrelacion`. Resuelve cuando el broker confirma. */
  private async responder(sobre: SobreComando, respuesta: RespuestaSaga): Promise<void> {
    const sobreRespuesta: SobreMensaje = {
      idMensaje: randomUUID(),
      idCorrelacion: sobre.idCorrelacion,
      tipo: respuesta.tipo,
      version: 1,
      fechaOcurrencia: this.reloj.ahora().toISOString(),
      origen: ORIGEN,
      datos: respuesta.datos,
    };
    await this.canal.sendToQueue(COLA_RESPUESTAS, Buffer.from(JSON.stringify(sobreRespuesta)), {
      persistent: true,
      contentType: 'application/json',
      messageId: sobreRespuesta.idMensaje,
      correlationId: sobreRespuesta.idCorrelacion,
      type: sobreRespuesta.tipo,
    });
  }
}
