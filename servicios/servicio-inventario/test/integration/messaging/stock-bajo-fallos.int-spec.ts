import request from 'supertest';
import { AmqpConnectionManager } from 'amqp-connection-manager';
import { EvaluacionStockBajo } from '../../../src/adapters/inbound/evaluacion-stock-bajo';
import { CONEXION_RABBITMQ } from '../../../src/adapters/outbound/messaging/conexion-rabbitmq';
import { PublicadorEventosRabbitmq } from '../../../src/adapters/outbound/messaging/publicador-eventos.rabbitmq';
import { RelojSistema } from '../../../src/adapters/outbound/reloj-sistema';
import {
  EventoDominio,
  PublicadorEventos,
} from '../../../src/application/ports/publicador-eventos.puerto';
import { AplicacionPrueba, PREFIJO, crearAplicacionPrueba, datosInsumo } from '../soporte/aplicacion-prueba';
import { OyenteEventos } from '../soporte/oyente-eventos';

/** El publicador real, que puede fallar a pedido del test. */
class PublicadorConFallas implements PublicadorEventos {
  fallar = false;

  constructor(private readonly real: PublicadorEventos) {}

  publicarEvento(evento: EventoDominio): Promise<void> {
    return this.fallar
      ? Promise.reject(new Error('Broker no disponible'))
      : this.real.publicarEvento(evento);
  }
}

async function crearInsumoYSalida(ap: AplicacionPrueba) {
  const admin = await ap.tokens.bearer(['administrador']);
  const creado = await request(ap.servidor)
    .post(`${PREFIJO}/insumos`)
    .set('Authorization', admin)
    .send(datosInsumo({ stockInicial: '100', nivelMinimo: '50' }));
  const salida = (cantidad: string) =>
    request(ap.servidor)
      .post(`${PREFIJO}/movimientos`)
      .set('Authorization', admin)
      .send({ idInsumo: creado.body.id, tipo: 'SALIDA', cantidad, motivo: 'Consumo' });
  return { id: creado.body.id as string, salida };
}

describe('Stock bajo cuando falla la publicación (Historia 3)', () => {
  let ap: AplicacionPrueba;
  let oyente: OyenteEventos;
  let publicador: PublicadorConFallas;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba((c) =>
      c.overrideProvider(PublicadorEventosRabbitmq).useFactory({
        factory: (conexion: AmqpConnectionManager, reloj: RelojSistema) =>
          (publicador = new PublicadorConFallas(new PublicadorEventosRabbitmq(conexion, reloj))),
        inject: [CONEXION_RABBITMQ, RelojSistema],
      }),
    );
    oyente = await OyenteEventos.escuchar('inventario.stock.bajo');
  });

  afterAll(async () => {
    await oyente.cerrar();
    await ap.cerrar();
  });

  it('escenarios 1 y 2: si falla, el movimiento se registra y la fecha no cambia; el siguiente movimiento publica', async () => {
    const { id, salida } = await crearInsumoYSalida(ap);
    publicador.fallar = true;
    const registrado = await salida('60');
    expect([registrado.status, registrado.body.stockResultante]).toEqual([201, '40.000']);

    await ap.app.get(EvaluacionStockBajo).esperarPendientes();
    const tras = await ap.conexion.collection('insumos').findOne({ _id: id as never });
    expect(tras?.fecha_ultima_alerta).toBeNull();
    expect(tras?.reserva_alerta_hasta).toBeNull();
    expect(await oyente.esperar(1, 500)).toHaveLength(0);

    publicador.fallar = false;
    expect((await salida('1')).status).toBe(201);
    await ap.app.get(EvaluacionStockBajo).esperarPendientes();
    const [evento] = await oyente.esperar(1);
    expect(evento.datos).toMatchObject({ idInsumo: id, stock: '39.000' });
    const final = await ap.conexion.collection('insumos').findOne({ _id: id as never });
    expect(final?.fecha_ultima_alerta).toBeInstanceOf(Date);
  });
});

describe('Con RabbitMQ inalcanzable (CE-SBJ-03, RNF-08)', () => {
  let ap: AplicacionPrueba;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba(undefined, { rabbitmqUrl: 'amqp://prueba:prueba@127.0.0.1:1' });
  });

  afterAll(() => ap.cerrar());

  it('los movimientos se registran igual y readiness informa RabbitMQ DOWN', async () => {
    const { id, salida } = await crearInsumoYSalida(ap);
    const inicio = Date.now();
    const registrado = await salida('60');
    expect(registrado.status).toBe(201);
    // La publicación no hace esperar la respuesta (CE-SBJ-04).
    expect(Date.now() - inicio).toBeLessThan(2000);

    const readiness = await request(ap.servidor).get('/salud/readiness');
    expect(readiness.status).toBe(503);
    expect(readiness.body.componentes).toEqual({ mongodb: 'UP', rabbitmq: 'DOWN' });

    // La publicación agota su tiempo límite (5 s) y no marca la alerta como enviada.
    await ap.app.get(EvaluacionStockBajo).esperarPendientes();
    const insumo = await ap.conexion.collection('insumos').findOne({ _id: id as never });
    expect(insumo?.fecha_ultima_alerta).toBeNull();
  }, 20_000);
});
