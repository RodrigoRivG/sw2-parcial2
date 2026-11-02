import request from 'supertest';
import { Decimal } from '../../../src/domain/shared/decimal';
import { AplicacionPrueba, PREFIJO, crearAplicacionPrueba, datosInsumo } from '../soporte/aplicacion-prueba';

describe('Concurrencia de movimientos (CE-MOV-01, CE-MOV-02, CE-MOV-03)', () => {
  let ap: AplicacionPrueba;
  let admin: string;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
    admin = await ap.tokens.bearer(['administrador']);
  });

  afterAll(() => ap.cerrar());

  async function crearInsumo(nombre: string, stockInicial: string): Promise<string> {
    const respuesta = await request(ap.servidor)
      .post(`${PREFIJO}/insumos`)
      .set('Authorization', admin)
      .send(datosInsumo({ nombre, stockInicial }));
    return respuesta.body.id;
  }

  const salida = (idInsumo: string, cantidad: string) =>
    request(ap.servidor)
      .post(`${PREFIJO}/movimientos`)
      .set('Authorization', admin)
      .send({ idInsumo, tipo: 'SALIDA', cantidad, motivo: 'Consumo' });

  /** stock guardado = Σ entradas − Σ salidas; y el último stock resultante coincide. */
  async function verificarConsistencia(idInsumo: string): Promise<string> {
    const insumo = await ap.conexion.collection('insumos').findOne({ _id: idInsumo as never });
    const movimientos = await ap.conexion
      .collection('movimientos_inventario')
      .find({ id_insumo: idInsumo })
      .sort({ fecha: -1, _id: -1 })
      .toArray();
    const suma = movimientos.reduce(
      (total, m) =>
        m.tipo === 'ENTRADA'
          ? total.plus(m.cantidad.toString())
          : total.minus(m.cantidad.toString()),
      new Decimal(0),
    );
    const stock = new Decimal(insumo?.stock.toString());
    expect(stock.equals(suma)).toBe(true);
    expect(stock.isNegative() && !stock.isZero()).toBe(false);
    const stocksResultantes = movimientos.map((m) => new Decimal(m.stock_resultante.toString()));
    expect(stocksResultantes.some((s) => s.equals(stock))).toBe(true);
    // CE-MOV-03: cada movimiento tiene su auditoría.
    const auditados = await ap.conexion
      .collection('registros_auditoria')
      .countDocuments({ id_entidad: { $in: movimientos.map((m) => m._id) } });
    expect(auditados).toBe(movimientos.length);
    return stock.toFixed(3);
  }

  it('50 salidas simultáneas sobre stock para 10 → exactamente 10 aceptadas y stock 0', async () => {
    const id = await crearInsumo('Herbicida Z', '10');
    const respuestas = await Promise.all(Array.from({ length: 50 }, () => salida(id, '1')));

    const aceptadas = respuestas.filter((r) => r.status === 201);
    const rechazadas = respuestas.filter((r) => r.status === 422);
    expect(aceptadas).toHaveLength(10);
    expect(rechazadas).toHaveLength(40);
    expect(rechazadas.every((r) => r.body.codigo === 'STOCK_INSUFICIENTE')).toBe(true);
    expect(await verificarConsistencia(id)).toBe('0.000');
    // Cada salida aceptada informa un stock resultante distinto: 9, 8, …, 0.
    expect(aceptadas.map((r) => r.body.stockResultante).sort()).toEqual(
      Array.from({ length: 10 }, (_, i) => `${i}.000`),
    );
  });

  it('entradas y salidas mezcladas en paralelo mantienen stock = Σ movimientos', async () => {
    const id = await crearInsumo('Fertilizante foliar', '5.5');
    await Promise.all([
      ...Array.from({ length: 10 }, () =>
        request(ap.servidor)
          .post(`${PREFIJO}/movimientos`)
          .set('Authorization', admin)
          .send({ idInsumo: id, tipo: 'ENTRADA', cantidad: '0.1', motivo: 'Compra' }),
      ),
      ...Array.from({ length: 10 }, () => salida(id, '0.7')),
    ]);
    const stock = new Decimal(await verificarConsistencia(id));
    expect(stock.greaterThanOrEqualTo(0)).toBe(true);
  });
});
