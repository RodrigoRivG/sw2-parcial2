import request from 'supertest';
import { AplicacionPrueba, PREFIJO, crearAplicacionPrueba, datosInsumo } from '../soporte/aplicacion-prueba';

describe('Concurrencia de insumos', () => {
  let ap: AplicacionPrueba;
  let admin: string;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
    admin = await ap.tokens.bearer(['administrador']);
  });

  afterAll(() => ap.cerrar());

  it('dos creaciones simultáneas con el mismo nombre → una 201 y una 409', async () => {
    const respuestas = await Promise.all(
      ['Fungicida X', 'fungicida x'].map((nombre) =>
        request(ap.servidor)
          .post(`${PREFIJO}/insumos`)
          .set('Authorization', admin)
          .send(datosInsumo({ nombre })),
      ),
    );
    expect(respuestas.map((r) => r.status).sort()).toEqual([201, 409]);
    expect(respuestas.find((r) => r.status === 409)?.body.codigo).toBe('NOMBRE_INSUMO_DUPLICADO');
    expect(
      await ap.conexion.collection('insumos').countDocuments({ nombre_normalizado: 'fungicida x' }),
    ).toBe(1);
    expect(await ap.conexion.collection('registros_auditoria').countDocuments()).toBe(1);
  });

  it('dos PUT simultáneos con la misma versión → uno 200 y otro 409 CONFLICTO_CONCURRENCIA', async () => {
    const creado = await request(ap.servidor)
      .post(`${PREFIJO}/insumos`)
      .set('Authorization', admin)
      .send(datosInsumo({ nombre: 'Insecticida Y' }));
    const respuestas = await Promise.all(
      ['5.10', '6.20'].map((costoUnitario) =>
        request(ap.servidor)
          .put(`${PREFIJO}/insumos/${creado.body.id}`)
          .set('Authorization', admin)
          .send(datosInsumo({ nombre: 'Insecticida Y', costoUnitario, version: 0 })),
      ),
    );
    expect(respuestas.map((r) => r.status).sort()).toEqual([200, 409]);
    expect(respuestas.find((r) => r.status === 409)?.body.codigo).toBe('CONFLICTO_CONCURRENCIA');
    const guardado = await ap.conexion.collection('insumos').findOne({ _id: creado.body.id });
    expect(guardado?.version).toBe(1);
  });
});
