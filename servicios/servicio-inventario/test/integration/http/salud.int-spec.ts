import request from 'supertest';
import { AplicacionPrueba, crearAplicacionPrueba } from '../soporte/aplicacion-prueba';

describe('Salud (constitución §9)', () => {
  let ap: AplicacionPrueba;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
  });

  afterAll(() => ap.cerrar());

  it('liveness y readiness responden UP con MongoDB y RabbitMQ disponibles', async () => {
    expect((await request(ap.servidor).get('/salud/liveness')).body).toEqual({ estado: 'UP' });
    // La conexión a RabbitMQ no bloquea el arranque: se espera a que conecte.
    let readiness = await request(ap.servidor).get('/salud/readiness');
    for (let i = 0; i < 50 && readiness.status !== 200; i++) {
      await new Promise((resolver) => setTimeout(resolver, 100));
      readiness = await request(ap.servidor).get('/salud/readiness');
    }
    expect(readiness.status).toBe(200);
    expect(readiness.body).toEqual({ estado: 'UP', componentes: { mongodb: 'UP', rabbitmq: 'UP' } });
  });

  it('readiness responde 503 si MongoDB no está; liveness sigue UP', async () => {
    await ap.conexion.dropDatabase();
    await ap.conexion.close();
    const readiness = await request(ap.servidor).get('/salud/readiness');
    expect(readiness.status).toBe(503);
    expect(readiness.body).toEqual({
      estado: 'DOWN',
      componentes: { mongodb: 'DOWN', rabbitmq: 'UP' },
    });
    expect((await request(ap.servidor).get('/salud')).status).toBe(503);
    expect((await request(ap.servidor).get('/salud/liveness')).status).toBe(200);
  });
});
