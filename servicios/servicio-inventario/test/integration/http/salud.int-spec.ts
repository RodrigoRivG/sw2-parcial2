import request from 'supertest';
import { AplicacionPrueba, crearAplicacionPrueba } from '../soporte/aplicacion-prueba';

describe('Salud (constitución §9)', () => {
  let ap: AplicacionPrueba;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
  });

  afterAll(() => ap.cerrar());

  it('liveness y readiness responden UP con MongoDB disponible', async () => {
    expect((await request(ap.servidor).get('/salud/liveness')).body).toEqual({ estado: 'UP' });
    const readiness = await request(ap.servidor).get('/salud/readiness');
    expect(readiness.status).toBe(200);
    expect(readiness.body).toEqual({ estado: 'UP', componentes: { mongodb: 'UP' } });
  });

  it('readiness responde 503 si MongoDB no está; liveness sigue UP', async () => {
    await ap.conexion.dropDatabase();
    await ap.conexion.close();
    const readiness = await request(ap.servidor).get('/salud/readiness');
    expect(readiness.status).toBe(503);
    expect(readiness.body).toEqual({ estado: 'DOWN', componentes: { mongodb: 'DOWN' } });
    expect((await request(ap.servidor).get('/salud')).status).toBe(503);
    expect((await request(ap.servidor).get('/salud/liveness')).status).toBe(200);
  });
});
