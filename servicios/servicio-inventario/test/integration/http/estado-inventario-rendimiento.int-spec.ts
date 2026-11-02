import { randomUUID } from 'node:crypto';
import request from 'supertest';
import { Types } from 'mongoose';
import { AplicacionPrueba, PREFIJO, crearAplicacionPrueba } from '../soporte/aplicacion-prueba';

describe('Rendimiento del estado del inventario (CE-EST-01, RNF-05)', () => {
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
        stock: Types.Decimal128.fromString(String(i % 200)),
        nivel_minimo: Types.Decimal128.fromString('50'),
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

  it.each([
    ['sin filtros', ''],
    ['solo stock bajo, por categoría', 'soloStockBajo=true&categoria=SEMILLA&tamanio=100'],
  ])('%s responde en menos de 3 s con 1.000 insumos', async (_caso, consulta) => {
    const autorizacion = await ap.tokens.bearer(['gerencia']);
    const inicio = Date.now();
    const respuesta = await request(ap.servidor)
      .get(`${PREFIJO}/estado-inventario?${consulta}`)
      .set('Authorization', autorizacion);
    expect(respuesta.status).toBe(200);
    expect(respuesta.body.items.length).toBeGreaterThan(0);
    expect(Date.now() - inicio).toBeLessThan(3000);
  });

  it('el resumen cuenta los 1.000 insumos (255 en stock bajo: stock 0 a 50 en cada ciclo de 200)', async () => {
    const respuesta = await request(ap.servidor)
      .get(`${PREFIJO}/estado-inventario?tamanio=1`)
      .set('Authorization', await ap.tokens.bearer(['gerencia']));
    expect(respuesta.body.resumen).toEqual({ totalInsumos: 1000, totalStockBajo: 255 });
  });
});
