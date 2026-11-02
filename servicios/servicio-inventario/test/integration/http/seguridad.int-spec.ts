import request from 'supertest';
import { AplicacionPrueba, PREFIJO, crearAplicacionPrueba, datosInsumo } from '../soporte/aplicacion-prueba';

describe('Seguridad (constitución §7, RNF-02)', () => {
  let ap: AplicacionPrueba;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
  });

  afterAll(() => ap.cerrar());

  const listar = (autorizacion?: string) => {
    const solicitud = request(ap.servidor)
      .get(`${PREFIJO}/insumos`)
      .set('X-Correlation-Id', 'corr-seguridad');
    return autorizacion ? solicitud.set('Authorization', autorizacion) : solicitud;
  };

  it('sin token → 401 NO_AUTENTICADO, con X-Correlation-Id en header y cuerpo', async () => {
    const respuesta = await listar();
    expect(respuesta.status).toBe(401);
    expect(respuesta.body).toEqual({
      codigo: 'NO_AUTENTICADO',
      mensaje: expect.any(String),
      detalles: [],
      idCorrelacion: 'corr-seguridad',
    });
    expect(respuesta.headers['x-correlation-id']).toBe('corr-seguridad');
  });

  it('esquema distinto de Bearer → 401', async () => {
    const token = await ap.tokens.token(['gerencia']);
    expect((await listar(`Basic ${token}`)).status).toBe(401);
  });

  it.each([
    ['firma de otra clave', { firmarConOtraClave: true }],
    ['emisor incorrecto', { emisor: 'http://otro-keycloak/realms/agro' }],
    ['audiencia incorrecta', { audiencia: 'servicio-gestion' }],
    ['token vencido', { expira: Math.floor(Date.now() / 1000) - 60 }],
  ])('%s → 401 NO_AUTENTICADO', async (_caso, opciones) => {
    const respuesta = await listar(await ap.tokens.bearer(['gerencia'], opciones));
    expect([respuesta.status, respuesta.body.codigo]).toEqual([401, 'NO_AUTENTICADO']);
  });

  it('rol sin permiso → 403 SIN_PERMISO con idCorrelacion, antes de validar el cuerpo', async () => {
    const respuesta = await request(ap.servidor)
      .post(`${PREFIJO}/insumos`)
      .set('Authorization', await ap.tokens.bearer(['gerencia']))
      .set('X-Correlation-Id', 'corr-403')
      .send({ cuerpo: 'inválido' });
    expect(respuesta.status).toBe(403);
    expect(respuesta.body).toMatchObject({ codigo: 'SIN_PERMISO', idCorrelacion: 'corr-403' });
    expect(respuesta.headers['x-correlation-id']).toBe('corr-403');
  });

  it('token válido con el rol correcto → 200', async () => {
    expect((await listar(await ap.tokens.bearer(['gerencia']))).status).toBe(200);
  });

  it('sin X-Correlation-Id se genera uno y se devuelve', async () => {
    const respuesta = await request(ap.servidor).get(`${PREFIJO}/insumos`);
    expect(respuesta.headers['x-correlation-id']).toMatch(/^[0-9a-f-]{36}$/);
    expect(respuesta.body.idCorrelacion).toBe(respuesta.headers['x-correlation-id']);
  });

  it('un X-Correlation-Id con caracteres no permitidos se reemplaza', async () => {
    const respuesta = await request(ap.servidor)
      .get(`${PREFIJO}/insumos`)
      .set('X-Correlation-Id', 'malo "inyectado"; nivel=error');
    expect(respuesta.headers['x-correlation-id']).toMatch(/^[0-9a-f-]{36}$/);
  });

  it.each(['/salud', '/salud/liveness', '/salud/readiness', '/api-docs-json'])(
    '%s responde sin token',
    async (ruta) => {
      expect((await request(ap.servidor).get(ruta)).status).toBe(200);
    },
  );

  it('OpenAPI documenta los cuatro endpoints de insumos con sus errores', async () => {
    const { body } = await request(ap.servidor).get('/api-docs-json');
    const insumos = body.paths[`${PREFIJO}/insumos`];
    const insumo = body.paths[`${PREFIJO}/insumos/{id}`];
    expect(Object.keys(insumos).sort()).toEqual(['get', 'post']);
    expect(Object.keys(insumo).sort()).toEqual(['get', 'put']);
    expect(Object.keys(insumos.post.responses).sort()).toEqual(
      ['201', '400', '401', '403', '409', '422'].sort(),
    );
    expect(Object.keys(insumo.put.responses).sort()).toEqual(
      ['200', '400', '401', '403', '404', '409', '422'].sort(),
    );
    expect(insumo.get.responses['404'].description).toContain('INSUMO_NO_ENCONTRADO');
  });

  it('la escritura exige administrador también con un cuerpo válido', async () => {
    const respuesta = await request(ap.servidor)
      .post(`${PREFIJO}/insumos`)
      .set('Authorization', await ap.tokens.bearer(['tecnico_campo']))
      .send(datosInsumo());
    expect(respuesta.status).toBe(403);
  });
});
