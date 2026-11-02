import request from 'supertest';
import { ConsultarInsumosCasoUso } from '../../../src/application/use-cases/consultar-insumos.caso-uso';
import { AplicacionPrueba, PREFIJO, crearAplicacionPrueba } from '../soporte/aplicacion-prueba';

describe('Formato común de errores (constitución §9)', () => {
  let ap: AplicacionPrueba;
  let gerencia: string;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba((constructor) =>
      constructor.overrideProvider(ConsultarInsumosCasoUso).useValue({
        listar: () => Promise.reject(new Error('detalle interno que no se debe exponer')),
        obtener: () => Promise.reject(new Error('detalle interno')),
      }),
    );
    gerencia = await ap.tokens.bearer(['gerencia', 'administrador']);
  });

  afterAll(() => ap.cerrar());

  it('JSON mal formado → 400 DATOS_INVALIDOS', async () => {
    const respuesta = await request(ap.servidor)
      .post(`${PREFIJO}/insumos`)
      .set('Authorization', gerencia)
      .set('Content-Type', 'application/json')
      .send('{"nombre": ');
    expect(respuesta.status).toBe(400);
    expect(respuesta.body).toMatchObject({ codigo: 'DATOS_INVALIDOS', idCorrelacion: expect.any(String) });
  });

  it('parámetros de consulta inválidos → 400 DATOS_INVALIDOS con detalle por campo', async () => {
    const respuesta = await request(ap.servidor)
      .get(`${PREFIJO}/insumos?tamanio=500&soloConStock=quizas&categoria=OTRA`)
      .set('Authorization', gerencia);
    expect(respuesta.status).toBe(400);
    expect(respuesta.body.codigo).toBe('DATOS_INVALIDOS');
    expect(respuesta.body.detalles.map((d: { campo: string }) => d.campo).sort()).toEqual([
      'categoria',
      'soloConStock',
      'tamanio',
    ]);
  });

  it('ID que no es UUID → 400 DATOS_INVALIDOS', async () => {
    const respuesta = await request(ap.servidor)
      .get(`${PREFIJO}/insumos/no-es-un-uuid`)
      .set('Authorization', gerencia);
    expect([respuesta.status, respuesta.body.codigo]).toEqual([400, 'DATOS_INVALIDOS']);
  });

  it.each([
    ['get', `${PREFIJO}/no-existe`],
    ['delete', `${PREFIJO}/insumos/0b6f1c6e-2f7a-4a7e-9a39-7d5a1c2b3d4e`],
  ] as const)('%s %s → 404 RECURSO_NO_ENCONTRADO', async (metodo, ruta) => {
    const respuesta = await request(ap.servidor)[metodo](ruta).set('Authorization', gerencia);
    expect([respuesta.status, respuesta.body.codigo]).toEqual([404, 'RECURSO_NO_ENCONTRADO']);
  });

  it('error inesperado → 500 ERROR_INTERNO sin exponer detalles', async () => {
    const respuesta = await request(ap.servidor)
      .get(`${PREFIJO}/insumos`)
      .set('Authorization', gerencia)
      .set('X-Correlation-Id', 'corr-500');
    expect(respuesta.status).toBe(500);
    expect(respuesta.body).toEqual({
      codigo: 'ERROR_INTERNO',
      mensaje: expect.any(String),
      detalles: [],
      idCorrelacion: 'corr-500',
    });
    expect(JSON.stringify(respuesta.body)).not.toContain('detalle interno');
  });
});
