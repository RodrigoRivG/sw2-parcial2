import { randomUUID } from 'node:crypto';
import request from 'supertest';
import {
  AplicacionPrueba,
  PREFIJO,
  crearAplicacionPrueba,
  crearInsumoApi,
  datosInsumo,
  stockDe,
} from '../soporte/aplicacion-prueba';
import { ClienteSaga } from '../soporte/cliente-saga';

describe('RestaurarInsumos (Historia 3, RN-08)', () => {
  let ap: AplicacionPrueba;
  let saga: ClienteSaga;
  let urea: string;
  let glifosato: string;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
    saga = await ClienteSaga.conectar();
  });

  afterAll(async () => {
    await saga.cerrar();
    await ap.cerrar();
  });

  beforeEach(async () => {
    for (const coleccion of ['insumos', 'movimientos_inventario', 'sagas_procesadas', 'registros_auditoria']) {
      await ap.conexion.collection(coleccion).deleteMany({});
    }
    urea = await crearInsumoApi(ap, { nombre: 'Urea', stockInicial: '200', costoUnitario: '4.85' });
    glifosato = await crearInsumoApi(ap, {
      nombre: 'Glifosato',
      unidad: 'LITRO',
      stockInicial: '50',
      costoUnitario: '38.20',
      nivelMinimo: '5',
    });
  });

  async function descontarYEsperar(items: { idInsumo: string; cantidad: string }[]) {
    const idSaga = randomUUID();
    const idLabor = randomUUID();
    saga.enviar('DescontarInsumos', { idSaga, idLabor, items });
    const respuesta = await saga.esperarRespuesta(idSaga);
    return { idSaga, idLabor, respuesta };
  }

  const restaurar = (idSaga: string, idLabor: string) =>
    saga.enviar('RestaurarInsumos', { idSaga, idLabor });

  const sagaGuardada = (idSaga: string) =>
    ap.conexion.collection('sagas_procesadas').findOne({ _id: idSaga as never });

  it('escenario 1: devuelve exactamente lo descontado, con motivo y auditoría, y responde sinEfecto=false', async () => {
    const { idSaga, idLabor } = await descontarYEsperar([
      { idInsumo: urea, cantidad: '100' },
      { idInsumo: glifosato, cantidad: '2.5' },
    ]);
    restaurar(idSaga, idLabor);
    const [, respuesta] = await saga.esperarRespuestas(idSaga, 2);
    expect(respuesta.tipo).toBe('InsumosRestaurados');
    expect(respuesta.datos).toEqual({
      idSaga,
      idLabor,
      sinEfecto: false,
      items: [
        { idInsumo: urea, cantidad: '100.000' },
        { idInsumo: glifosato, cantidad: '2.500' },
      ],
    });
    expect(await stockDe(ap, urea)).toBe('200.000');
    expect(await stockDe(ap, glifosato)).toBe('50.000');
    const entradas = await ap.conexion
      .collection('movimientos_inventario')
      .find({ id_saga: idSaga, tipo: 'ENTRADA' })
      .toArray();
    expect(entradas).toHaveLength(2);
    expect(entradas.every((m) => m.motivo === `Compensación de saga ${idSaga}` && m.id_labor === idLabor)).toBe(true);
    expect(
      await ap.conexion.collection('registros_auditoria').countDocuments({ accion: 'RESTAURAR_INSUMOS_SAGA' }),
    ).toBe(2);
    expect(await sagaGuardada(idSaga)).toMatchObject({ resultado: 'RESTAURADO' });
  });

  it('escenario 2: sin descuento previo → sinEfecto=true y el idSaga queda RESTAURADO', async () => {
    const idSaga = randomUUID();
    restaurar(idSaga, randomUUID());
    const respuesta = await saga.esperarRespuesta(idSaga);
    expect(respuesta.datos).toMatchObject({ sinEfecto: true, items: [] });
    expect(await sagaGuardada(idSaga)).toMatchObject({ resultado: 'RESTAURADO', descuento: null });
  });

  it('escenario 3: un idSaga rechazado → sinEfecto=true y conserva RECHAZADO', async () => {
    const { idSaga, idLabor, respuesta } = await descontarYEsperar([{ idInsumo: urea, cantidad: '999' }]);
    expect(respuesta.datos.codigo).toBe('STOCK_INSUFICIENTE');
    restaurar(idSaga, idLabor);
    const [, restaurado] = await saga.esperarRespuestas(idSaga, 2);
    expect(restaurado.datos).toMatchObject({ sinEfecto: true, items: [] });
    expect(await sagaGuardada(idSaga)).toMatchObject({ resultado: 'RECHAZADO' });
    expect(await stockDe(ap, urea)).toBe('200.000');
  });

  it('escenario 4: la compensación repetida devuelve la misma respuesta sin movimientos nuevos', async () => {
    const { idSaga, idLabor } = await descontarYEsperar([{ idInsumo: urea, cantidad: '30' }]);
    restaurar(idSaga, idLabor);
    restaurar(idSaga, idLabor);
    restaurar(idSaga, idLabor);
    const respuestas = (await saga.esperarRespuestas(idSaga, 4)).slice(1);
    expect(respuestas).toHaveLength(3);
    expect(new Set(respuestas.map((r) => JSON.stringify(r.datos))).size).toBe(1);
    expect(
      await ap.conexion.collection('movimientos_inventario').countDocuments({ id_saga: idSaga, tipo: 'ENTRADA' }),
    ).toBe(1);
    expect(await stockDe(ap, urea)).toBe('200.000');
  });

  it('escenario 5: un DescontarInsumos repetido tras restaurar repite el original y no toca el stock', async () => {
    const items = [{ idInsumo: urea, cantidad: '40' }];
    const { idSaga, idLabor, respuesta } = await descontarYEsperar(items);
    restaurar(idSaga, idLabor);
    await saga.esperarRespuestas(idSaga, 2);
    saga.enviar('DescontarInsumos', { idSaga, idLabor, items });
    const [, , repetido] = await saga.esperarRespuestas(idSaga, 3);
    expect(repetido.tipo).toBe('InsumosDescontados');
    expect(repetido.datos).toEqual(respuesta.datos);
    expect(await stockDe(ap, urea)).toBe('200.000');
  });

  it('escenario 6: las entradas de compensación usan el costo de las salidas originales', async () => {
    const { idSaga, idLabor } = await descontarYEsperar([{ idInsumo: urea, cantidad: '10' }]);
    const cambio = await request(ap.servidor)
      .put(`${PREFIJO}/insumos/${urea}`)
      .set('Authorization', await ap.tokens.bearer(['administrador']))
      .send(datosInsumo({ nombre: 'Urea', costoUnitario: '7.77', version: 0 }));
    expect(cambio.status).toBe(200);
    restaurar(idSaga, idLabor);
    await saga.esperarRespuestas(idSaga, 2);
    const entrada = await ap.conexion
      .collection('movimientos_inventario')
      .findOne({ id_saga: idSaga, tipo: 'ENTRADA' });
    expect(String(entrada?.costo_unitario)).toBe('4.85');
  });

  it('CE-SAG-03: descuento y restauración del mismo idSaga en paralelo, en ambos órdenes → stock inicial', async () => {
    for (const restauracionPrimero of [false, true, false, true]) {
      const idSaga = randomUUID();
      const idLabor = randomUUID();
      const descuento = { idSaga, idLabor, items: [{ idInsumo: urea, cantidad: '25' }] };
      if (restauracionPrimero) {
        restaurar(idSaga, idLabor);
        saga.enviar('DescontarInsumos', descuento);
      } else {
        saga.enviar('DescontarInsumos', descuento);
        restaurar(idSaga, idLabor);
      }
      const respuestas = await saga.esperarRespuestas(idSaga, 2);
      expect(respuestas).toHaveLength(2);
      expect(await sagaGuardada(idSaga)).toMatchObject({ resultado: 'RESTAURADO' });
    }
    expect(await stockDe(ap, urea)).toBe('200.000');
  });
});
