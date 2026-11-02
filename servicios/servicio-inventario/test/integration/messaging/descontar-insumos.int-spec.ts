import { randomUUID } from 'node:crypto';
import request from 'supertest';
import {
  AplicacionPrueba,
  PREFIJO,
  crearAplicacionPrueba,
  crearInsumoApi,
  stockDe,
} from '../soporte/aplicacion-prueba';
import { ClienteSaga } from '../soporte/cliente-saga';

describe('DescontarInsumos (spec-descuento-saga.md, Historia 1)', () => {
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
      categoria: 'FITOSANITARIO',
      unidad: 'LITRO',
      stockInicial: '50',
      costoUnitario: '38.20',
      nivelMinimo: '5',
    });
  });

  const descontar = (items: { idInsumo: string; cantidad: string }[], idSaga = randomUUID()) => {
    const idLabor = randomUUID();
    saga.enviar('DescontarInsumos', { idSaga, idLabor, items });
    return { idSaga, idLabor };
  };

  it('escenario 1: descuenta todo, crea las salidas y responde InsumosDescontados con el costo total', async () => {
    const inicio = Date.now();
    const { idSaga, idLabor } = descontar([
      { idInsumo: urea, cantidad: '100' },
      { idInsumo: glifosato, cantidad: '2.5' },
    ]);
    const respuesta = await saga.esperarRespuesta(idSaga);
    expect(Date.now() - inicio).toBeLessThan(1000); // CE-SAG-05

    expect(respuesta).toEqual({
      idMensaje: expect.stringMatching(/^[0-9a-f-]{36}$/),
      idCorrelacion: idSaga,
      tipo: 'InsumosDescontados',
      version: 1,
      fechaOcurrencia: expect.any(String),
      origen: 'servicio-inventario',
      datos: {
        idSaga,
        idLabor,
        costoTotal: '580.50',
        items: [
          { idInsumo: urea, cantidad: '100.000', costoUnitario: '4.8500' },
          { idInsumo: glifosato, cantidad: '2.500', costoUnitario: '38.2000' },
        ],
      },
    });
    expect(await stockDe(ap, urea)).toBe('100.000');
    expect(await stockDe(ap, glifosato)).toBe('47.500');

    const salidas = await ap.conexion
      .collection('movimientos_inventario')
      .find({ id_saga: idSaga })
      .toArray();
    expect(salidas).toHaveLength(2);
    expect(salidas.every((m) => m.tipo === 'SALIDA' && m.id_labor === idLabor)).toBe(true);
    expect(salidas.every((m) => m.motivo === `Labor ${idLabor}` && m.actor === 'servicio-operaciones')).toBe(true);
    expect(
      await ap.conexion
        .collection('registros_auditoria')
        .countDocuments({ accion: 'DESCONTAR_INSUMOS_SAGA', actor: 'servicio-operaciones', id_correlacion: idSaga }),
    ).toBe(2);
    expect(await ap.conexion.collection('sagas_procesadas').findOne({ _id: idSaga as never })).toMatchObject({
      resultado: 'DESCONTADO',
      id_labor: idLabor,
    });
  });

  it('spec-movimientos, Historia 3, escenario 4: el listado muestra idSaga, idLabor y el servicio como actor', async () => {
    const { idSaga, idLabor } = descontar([{ idInsumo: urea, cantidad: '10' }]);
    await saga.esperarRespuesta(idSaga);
    const listado = await request(ap.servidor)
      .get(`${PREFIJO}/movimientos?idSaga=${idSaga}`)
      .set('Authorization', await ap.tokens.bearer(['gerencia']));
    expect(listado.body.items).toEqual([
      expect.objectContaining({ tipo: 'SALIDA', idSaga, idLabor, actor: 'servicio-operaciones' }),
    ]);
  });

  it('escenario 2: redondeo final mitad hacia arriba (3 × 0,1235 → 0.37; 1 × 0,125 → 0.13)', async () => {
    const barato = await crearInsumoApi(ap, { nombre: 'Barato', stockInicial: '10', costoUnitario: '0.1235' });
    const medio = await crearInsumoApi(ap, { nombre: 'Medio', stockInicial: '10', costoUnitario: '0.125' });
    const primera = descontar([{ idInsumo: barato, cantidad: '3' }]);
    const segunda = descontar([{ idInsumo: medio, cantidad: '1' }]);
    expect((await saga.esperarRespuesta(primera.idSaga)).datos.costoTotal).toBe('0.37');
    expect((await saga.esperarRespuesta(segunda.idSaga)).datos.costoTotal).toBe('0.13');
  });

  it('escenario 3: insumos sin costo → costoTotal "0.00"', async () => {
    const donado = await crearInsumoApi(ap, { nombre: 'Donado', stockInicial: '10', costoUnitario: '0' });
    const { idSaga } = descontar([{ idInsumo: donado, cantidad: '4' }]);
    const respuesta = await saga.esperarRespuesta(idSaga);
    expect([respuesta.tipo, respuesta.datos.costoTotal]).toEqual(['InsumosDescontados', '0.00']);
  });

  it('escenario 4: un insumo no alcanza → no se descuenta ninguno (RN-04) y STOCK_INSUFICIENTE', async () => {
    const { idSaga } = descontar([
      { idInsumo: urea, cantidad: '100' },
      { idInsumo: glifosato, cantidad: '50.001' },
    ]);
    const respuesta = await saga.esperarRespuesta(idSaga);
    expect(respuesta.tipo).toBe('InsumosRechazados');
    expect(respuesta.datos).toMatchObject({
      idSaga,
      codigo: 'STOCK_INSUFICIENTE',
      insumosAfectados: [{ idInsumo: glifosato, cantidadSolicitada: '50.001', stockDisponible: '50.000' }],
    });
    expect(await stockDe(ap, urea)).toBe('200.000');
    expect(await ap.conexion.collection('movimientos_inventario').countDocuments({ id_saga: idSaga })).toBe(0);
    expect(await ap.conexion.collection('sagas_procesadas').findOne({ _id: idSaga as never })).toMatchObject({
      resultado: 'RECHAZADO',
    });
  });

  it('escenario 5: un insumo inexistente → INSUMO_NO_ENCONTRADO con stockDisponible null', async () => {
    const inexistente = randomUUID();
    const { idSaga } = descontar([
      { idInsumo: urea, cantidad: '1' },
      { idInsumo: inexistente, cantidad: '1' },
    ]);
    const respuesta = await saga.esperarRespuesta(idSaga);
    expect(respuesta.datos).toMatchObject({
      codigo: 'INSUMO_NO_ENCONTRADO',
      insumosAfectados: [{ idInsumo: inexistente, cantidadSolicitada: '1.000', stockDisponible: null }],
    });
    expect(await stockDe(ap, urea)).toBe('200.000');
  });

  it.each([
    ['items vacío', () => []],
    ['insumo repetido', () => [{ idInsumo: urea, cantidad: '1' }, { idInsumo: urea, cantidad: '2' }]],
  ])('escenario 6: %s → DATOS_INVALIDOS sin tocar el stock', async (_caso, items) => {
    const { idSaga } = descontar(items());
    const respuesta = await saga.esperarRespuesta(idSaga);
    expect(respuesta.datos).toMatchObject({ idSaga, codigo: 'DATOS_INVALIDOS' });
    expect(await stockDe(ap, urea)).toBe('200.000');
    expect(await ap.conexion.collection('sagas_procesadas').countDocuments({ _id: idSaga as never })).toBe(0);
  });

  it('caso borde: cantidad decimal para un insumo con UNIDAD → DATOS_INVALIDOS con ese insumo', async () => {
    const trampa = await crearInsumoApi(ap, { nombre: 'Trampa', unidad: 'UNIDAD', stockInicial: '10', nivelMinimo: '1' });
    const { idSaga } = descontar([{ idInsumo: trampa, cantidad: '1.5' }]);
    const respuesta = await saga.esperarRespuesta(idSaga);
    expect(respuesta.datos).toMatchObject({
      codigo: 'DATOS_INVALIDOS',
      insumosAfectados: [{ idInsumo: trampa, cantidadSolicitada: '1.500', stockDisponible: '10.000' }],
    });
  });

  it('escenario 7: restaurado sin descuento previo → el descuento tardío se rechaza con SAGA_COMPENSADA', async () => {
    const idSaga = randomUUID();
    saga.enviar('RestaurarInsumos', { idSaga, idLabor: randomUUID() });
    expect((await saga.esperarRespuesta(idSaga)).tipo).toBe('InsumosRestaurados');
    descontar([{ idInsumo: urea, cantidad: '10' }], idSaga);
    const [, tardio] = await saga.esperarRespuestas(idSaga, 2);
    expect(tardio.tipo).toBe('InsumosRechazados');
    expect(tardio.datos).toMatchObject({ codigo: 'SAGA_COMPENSADA' });
    expect(await stockDe(ap, urea)).toBe('200.000');
  });
});
