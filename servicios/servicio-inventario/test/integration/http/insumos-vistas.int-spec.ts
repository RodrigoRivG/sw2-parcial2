import request from 'supertest';
import { AplicacionPrueba, PREFIJO, crearAplicacionPrueba, datosInsumo } from '../soporte/aplicacion-prueba';

const CAMPOS_REDUCIDOS = ['categoria', 'id', 'nombre', 'stock', 'unidad'];

describe('Vistas del insumo según el rol (CE-INS-03)', () => {
  let ap: AplicacionPrueba;
  let id: string;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
    const creado = await request(ap.servidor)
      .post(`${PREFIJO}/insumos`)
      .set('Authorization', await ap.tokens.bearer(['administrador']))
      .send(datosInsumo());
    id = creado.body.id;
  });

  afterAll(() => ap.cerrar());

  async function leer(roles: string[]) {
    const autorizacion = await ap.tokens.bearer(roles);
    const listado = await request(ap.servidor)
      .get(`${PREFIJO}/insumos`)
      .set('Authorization', autorizacion);
    const detalle = await request(ap.servidor)
      .get(`${PREFIJO}/insumos/${id}`)
      .set('Authorization', autorizacion);
    expect([listado.status, detalle.status]).toEqual([200, 200]);
    return { enListado: listado.body.items[0], detalle: detalle.body };
  }

  it('escenario 4: solo tecnico_campo → vista reducida, sin costo ni nivel mínimo', async () => {
    const { enListado, detalle } = await leer(['tecnico_campo']);
    for (const vista of [enListado, detalle]) {
      expect(Object.keys(vista).sort()).toEqual(CAMPOS_REDUCIDOS);
      expect(vista).not.toHaveProperty('costoUnitario');
    }
  });

  it.each([
    [['tecnico_campo', 'gerencia']],
    [['administrador']],
    [['gerencia']],
    [['lectura_inventario']],
  ])('escenarios 5 y 6: %j → vista completa', async (roles) => {
    const { enListado, detalle } = await leer(roles);
    for (const vista of [enListado, detalle]) {
      expect(vista).toMatchObject({ costoUnitario: '4.8500', nivelMinimo: '50.000', version: 0 });
    }
  });

  it('escenario 6: lectura_inventario no puede modificar (RN-14)', async () => {
    const respuesta = await request(ap.servidor)
      .put(`${PREFIJO}/insumos/${id}`)
      .set('Authorization', await ap.tokens.bearer(['lectura_inventario']))
      .send(datosInsumo({ version: 0 }));
    expect([respuesta.status, respuesta.body.codigo]).toEqual([403, 'SIN_PERMISO']);
  });

  it('un token sin roles del servicio no puede leer', async () => {
    const respuesta = await request(ap.servidor)
      .get(`${PREFIJO}/insumos`)
      .set('Authorization', await ap.tokens.bearer(['otro_rol']));
    expect([respuesta.status, respuesta.body.codigo]).toEqual([403, 'SIN_PERMISO']);
  });
});
