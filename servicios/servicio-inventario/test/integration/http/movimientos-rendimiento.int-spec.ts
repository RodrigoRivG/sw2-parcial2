import { randomUUID } from 'node:crypto';
import request from 'supertest';
import { Types } from 'mongoose';
import { AplicacionPrueba, PREFIJO, crearAplicacionPrueba } from '../soporte/aplicacion-prueba';

describe('Rendimiento del listado de movimientos (CE-MOV-04, RNF-05)', () => {
  let ap: AplicacionPrueba;
  const idInsumo = randomUUID();

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
    const inicio = Date.now() - 10_000 * 60_000;
    await ap.conexion.collection<{ _id: string }>('movimientos_inventario').insertMany(
      Array.from({ length: 10_000 }, (_, i) => ({
        _id: randomUUID(),
        id_insumo: i % 2 === 0 ? idInsumo : randomUUID(),
        tipo: i % 3 === 0 ? 'SALIDA' : 'ENTRADA',
        cantidad: Types.Decimal128.fromString('1'),
        stock_resultante: Types.Decimal128.fromString(String(i)),
        costo_unitario: Types.Decimal128.fromString('4.85'),
        motivo: `Movimiento ${i}`,
        actor: 'admin-1',
        fecha: new Date(inicio + i * 60_000),
      })),
    );
  });

  afterAll(() => ap.cerrar());

  it.each([
    ['sin filtros', ''],
    ['por insumo y tipo', `idInsumo=${idInsumo}&tipo=SALIDA`],
    ['por rango de fechas, última página', 'desde=2020-01-01T00:00:00Z&pagina=49&tamanio=100'],
  ])('%s responde en menos de 3 s', async (_caso, consulta) => {
    const autorizacion = await ap.tokens.bearer(['gerencia']);
    const inicio = Date.now();
    const respuesta = await request(ap.servidor)
      .get(`${PREFIJO}/movimientos?${consulta}`)
      .set('Authorization', autorizacion);
    expect(respuesta.status).toBe(200);
    expect(respuesta.body.items.length).toBeGreaterThan(0);
    expect(Date.now() - inicio).toBeLessThan(3000);
  });
});
