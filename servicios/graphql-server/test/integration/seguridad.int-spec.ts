import request from 'supertest';
import { crearAplicacion, type Aplicacion } from '../../src/app';
import { PERMISOS } from '../../src/seguridad/permisos';
import * as d from '../soporte/datos';
import { consultar, GatewaySimulado } from '../soporte/gateway-simulado';

let gateway: GatewaySimulado;
let aplicacion: Aplicacion;

beforeAll(async () => {
  gateway = await GatewaySimulado.iniciar();
  aplicacion = await crearAplicacion(gateway.configuracion());
});
afterAll(async () => {
  await aplicacion.detener();
  await gateway.detener();
});
beforeEach(() => gateway.reiniciar());

const CONSULTA = '{ campanias { total } }';

/** Historia 6 y CORS (D-GQL-07). */
describe('seguridad', () => {
  it.each([
    ['sin token', null],
    ['firmado con otra clave', { ajena: true }],
    ['de otro emisor', { iss: 'http://otro/realms/agro' }],
    ['vencido', { vence: Math.floor(Date.now() / 1000) - 10 }],
    ['sin graphql-server en aud', { aud: 'servicio-gestion' }],
  ])('token %s → 401 NO_AUTENTICADO sin llamar a ningún servicio', async (_caso, opciones) => {
    const token = opciones === null ? null : await gateway.firmar(opciones);
    const respuesta = await consultar(aplicacion.app, token, CONSULTA, { 'X-Correlation-Id': 'abc-123' });
    expect(respuesta.status).toBe(401);
    expect(respuesta.body).toEqual({
      codigo: 'NO_AUTENTICADO',
      mensaje: 'Debe iniciar sesión para continuar.',
      detalles: [],
      idCorrelacion: 'abc-123',
    });
    expect(gateway.llamadas).toHaveLength(0);
  });

  it('técnico de campo → 403 SIN_PERMISO sin llamar a ningún servicio', async () => {
    const respuesta = await consultar(aplicacion.app, await gateway.firmar({ roles: ['tecnico_campo'] }), CONSULTA);
    expect(respuesta.status).toBe(403);
    expect(respuesta.body.codigo).toBe('SIN_PERMISO');
    expect(gateway.llamadas).toHaveLength(0);
  });

  it('administrador no recibe los campos de IA (sin llamar a IA); gerencia y multirol sí', async () => {
    expect(Object.entries(PERMISOS).filter(([, roles]) => !roles.includes('administrador')).map(([c]) => c)).toEqual([
      'Query.analisis',
      'Query.analisisPorId',
      'Campania.predicciones',
    ]);
    gateway.registrar(`${d.G}/campanias/c1`, { cuerpo: d.campania('c1') });
    gateway.registrar(`${d.G}/campanias/c1/indicadores`, { cuerpo: d.indicadores('c1') });
    gateway.registrar(`${d.IA}/predicciones`, { cuerpo: d.pagina([]) });
    gateway.registrar(`${d.IA}/analisis`, { cuerpo: d.pagina([]) });
    const consulta = '{ campania(id: "c1") { indicadores { costoTotal } predicciones { total } } analisis { total } }';

    const admin = await consultar(aplicacion.app, await gateway.firmar({ roles: ['administrador'] }), consulta);
    expect(admin.body.data).toEqual({ campania: { indicadores: { costoTotal: '820.50' }, predicciones: null }, analisis: null });
    expect(admin.body.errors.map((e: { extensions: { codigo: string } }) => e.extensions.codigo)).toEqual([
      'SIN_PERMISO',
      'SIN_PERMISO',
    ]);
    expect(gateway.llamadasA(`${d.IA}/analisis`)).toHaveLength(0);
    expect(gateway.llamadasA(`${d.IA}/predicciones`)).toHaveLength(0);

    for (const roles of [['gerencia'], ['administrador', 'gerencia']]) {
      const respuesta = await consultar(aplicacion.app, await gateway.firmar({ roles }), consulta);
      expect(respuesta.body.errors).toBeUndefined();
      expect(respuesta.body.data.analisis).toEqual({ total: 0 });
    }
  });

  it('una mutation se rechaza en la validación con DATOS_INVALIDOS', async () => {
    const respuesta = await consultar(aplicacion.app, await gateway.firmar(), 'mutation { borrar }');
    expect(respuesta.status).toBe(400);
    expect(respuesta.body.errors[0].extensions.codigo).toBe('DATOS_INVALIDOS');
  });

  it.each([
    ['responde 500', { estado: 500 }],
    ['no responde', { nuncaResponde: true }],
  ])('JWKS que %s → 503 AUTENTICACION_NO_DISPONIBLE en menos de 2 s', async (_caso, jwks) => {
    // Aplicación nueva: sin claves en caché.
    const otra = await crearAplicacion(gateway.configuracion());
    gateway.jwks = jwks;
    const inicio = Date.now();
    const respuesta = await consultar(otra.app, await gateway.firmar(), CONSULTA);
    expect(respuesta.status).toBe(503);
    expect(respuesta.body.codigo).toBe('AUTENTICACION_NO_DISPONIBLE');
    expect(Date.now() - inicio).toBeLessThan(2000);
    await otra.detener();
  });
});

describe('CORS', () => {
  const SANDBOX = 'https://sandbox.embed.apollographql.com';

  it('fuera de producción, Apollo Sandbox pasa la verificación previa sin token y sus consultas exigen token', async () => {
    const previa = await request(aplicacion.app)
      .options('/api/graphql')
      .set('Origin', SANDBOX)
      .set('Access-Control-Request-Method', 'POST')
      .set('Access-Control-Request-Headers', 'authorization,content-type');
    expect(previa.status).toBe(204);
    expect(previa.headers).toMatchObject({
      'access-control-allow-origin': SANDBOX,
      'access-control-allow-headers': 'authorization,content-type',
    });

    const sinToken = await consultar(aplicacion.app, null, CONSULTA, { Origin: SANDBOX });
    expect(sinToken.status).toBe(401);
    expect(sinToken.headers['access-control-allow-origin']).toBe(SANDBOX);
    expect(gateway.llamadas).toHaveLength(0);
  });

  it('otro origen, o cualquier origen en producción, no recibe headers de CORS', async () => {
    const produccion = await crearAplicacion(gateway.configuracion({ produccion: true }));
    for (const [app, origen] of [
      [aplicacion.app, 'http://localhost:9000'],
      [produccion.app, SANDBOX],
    ] as const) {
      const previa = await request(app).options('/api/graphql').set('Origin', origen).set('Access-Control-Request-Method', 'POST');
      const consulta = await consultar(app, await gateway.firmar(), '{ __typename }', { Origin: origen });
      expect(previa.headers['access-control-allow-origin']).toBeUndefined();
      expect(consulta.headers['access-control-allow-origin']).toBeUndefined();
    }
    await produccion.detener();
  });
});
