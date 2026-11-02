import { randomUUID } from 'node:crypto';
import request from 'supertest';
import { Types } from 'mongoose';
import { AplicacionPrueba, PREFIJO, crearAplicacionPrueba } from '../soporte/aplicacion-prueba';

describe('Rendimiento de las consultas de insumos (CE-INS-02, RNF-05)', () => {
  let ap: AplicacionPrueba;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
    const ahora = new Date();
    await ap.conexion.collection<{ _id: string }>('insumos').insertMany(
      Array.from({ length: 1000 }, (_, i) => ({
        _id: randomUUID(),
        nombre: `Insumo ${i}`,
        nombre_normalizado: `insumo ${i}`,
        categoria: ['SEMILLA', 'FERTILIZANTE', 'FITOSANITARIO'][i % 3],
        unidad: 'KILOGRAMO',
        stock: Types.Decimal128.fromString(String(i)),
        nivel_minimo: Types.Decimal128.fromString('10'),
        costo_unitario: Types.Decimal128.fromString('1.5'),
        descripcion: null,
        tiene_movimientos: true,
        fecha_ultima_alerta: null,
        reserva_alerta_hasta: null,
        version: 0,
        fecha_creacion: ahora,
        fecha_actualizacion: ahora,
      })),
    );
  });

  afterAll(() => ap.cerrar());

  it('listado y detalle responden en menos de 3 s con 1.000 insumos', async () => {
    const autorizacion = await ap.tokens.bearer(['gerencia']);

    let inicio = Date.now();
    const listado = await request(ap.servidor)
      .get(`${PREFIJO}/insumos?tamanio=100&soloConStock=true&nombre=insumo`)
      .set('Authorization', autorizacion);
    expect(listado.status).toBe(200);
    expect(listado.body.total).toBe(999);
    expect(Date.now() - inicio).toBeLessThan(3000);

    inicio = Date.now();
    const detalle = await request(ap.servidor)
      .get(`${PREFIJO}/insumos/${listado.body.items[0].id}`)
      .set('Authorization', autorizacion);
    expect(detalle.status).toBe(200);
    expect(Date.now() - inicio).toBeLessThan(3000);
  });
});
