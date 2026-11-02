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

describe('Idempotencia de DescontarInsumos (Historia 2, RN-09)', () => {
  let ap: AplicacionPrueba;
  let saga: ClienteSaga;
  let admin: string;
  let urea: string;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
    saga = await ClienteSaga.conectar();
    admin = await ap.tokens.bearer(['administrador']);
  });

  afterAll(async () => {
    await saga.cerrar();
    await ap.cerrar();
  });

  beforeEach(async () => {
    for (const coleccion of ['insumos', 'movimientos_inventario', 'sagas_procesadas']) {
      await ap.conexion.collection(coleccion).deleteMany({});
    }
    urea = await crearInsumoApi(ap, { nombre: 'Urea', stockInicial: '200', costoUnitario: '4.85' });
  });

  const salidasDe = (idSaga: string) =>
    ap.conexion.collection('movimientos_inventario').countDocuments({ id_saga: idSaga });

  it('escenario 1: el mismo idSaga con el mismo o distinto idMensaje no descuenta dos veces', async () => {
    const datos = { idSaga: randomUUID(), idLabor: randomUUID(), items: [{ idInsumo: urea, cantidad: '100' }] };
    const idMensaje = saga.enviar('DescontarInsumos', datos);
    const primera = await saga.esperarRespuesta(datos.idSaga);
    saga.enviar('DescontarInsumos', datos, { idMensaje });
    saga.enviar('DescontarInsumos', datos);
    const respuestas = await saga.esperarRespuestas(datos.idSaga, 3);
    expect(respuestas).toHaveLength(3);
    expect(respuestas.map((r) => r.datos)).toEqual([primera.datos, primera.datos, primera.datos]);
    expect(await stockDe(ap, urea)).toBe('100.000');
    expect(await salidasDe(datos.idSaga)).toBe(1);
  });

  it('escenario 2: con el costo unitario cambiado, la respuesta repetida trae el costo original', async () => {
    const datos = { idSaga: randomUUID(), idLabor: randomUUID(), items: [{ idInsumo: urea, cantidad: '100' }] };
    saga.enviar('DescontarInsumos', datos);
    expect((await saga.esperarRespuesta(datos.idSaga)).datos.costoTotal).toBe('485.00');
    const cambio = await request(ap.servidor)
      .put(`${PREFIJO}/insumos/${urea}`)
      .set('Authorization', admin)
      .send(datosInsumo({ nombre: 'Urea', costoUnitario: '9.99', version: 0 }));
    expect(cambio.status).toBe(200);
    saga.enviar('DescontarInsumos', datos);
    const [, repetida] = await saga.esperarRespuestas(datos.idSaga, 2);
    expect(repetida.datos).toMatchObject({
      costoTotal: '485.00',
      items: [{ idInsumo: urea, cantidad: '100.000', costoUnitario: '4.8500' }],
    });
  });

  it('escenario 3: un rechazo se repite aunque ahora sí haya stock', async () => {
    const datos = { idSaga: randomUUID(), idLabor: randomUUID(), items: [{ idInsumo: urea, cantidad: '300' }] };
    saga.enviar('DescontarInsumos', datos);
    const rechazo = await saga.esperarRespuesta(datos.idSaga);
    expect(rechazo.datos.codigo).toBe('STOCK_INSUFICIENTE');
    const entrada = await request(ap.servidor)
      .post(`${PREFIJO}/movimientos`)
      .set('Authorization', admin)
      .send({ idInsumo: urea, tipo: 'ENTRADA', cantidad: '500', motivo: 'Compra' });
    expect(entrada.status).toBe(201);
    saga.enviar('DescontarInsumos', datos);
    const [, repetido] = await saga.esperarRespuestas(datos.idSaga, 2);
    expect(repetido.datos).toEqual(rechazo.datos);
    expect(await stockDe(ap, urea)).toBe('700.000');
  });

  it('escenario 4: repetido con otros items → se responde el resultado original', async () => {
    const idSaga = randomUUID();
    const idLabor = randomUUID();
    saga.enviar('DescontarInsumos', { idSaga, idLabor, items: [{ idInsumo: urea, cantidad: '10' }] });
    const original = await saga.esperarRespuesta(idSaga);
    saga.enviar('DescontarInsumos', { idSaga, idLabor, items: [{ idInsumo: urea, cantidad: '50' }] });
    const [, repetida] = await saga.esperarRespuestas(idSaga, 2);
    expect(repetida.datos).toEqual(original.datos);
    expect(await stockDe(ap, urea)).toBe('190.000');
  });

  it('escenario 5 y CE-SAG-02: 100 entregas simultáneas del mismo comando → un solo descuento', async () => {
    const datos = { idSaga: randomUUID(), idLabor: randomUUID(), items: [{ idInsumo: urea, cantidad: '1.5' }] };
    for (let i = 0; i < 100; i++) {
      saga.enviar('DescontarInsumos', datos);
    }
    const respuestas = await saga.esperarRespuestas(datos.idSaga, 100, 30_000);
    expect(respuestas).toHaveLength(100);
    expect(new Set(respuestas.map((r) => JSON.stringify(r.datos))).size).toBe(1);
    expect(respuestas[0].tipo).toBe('InsumosDescontados');
    expect(await stockDe(ap, urea)).toBe('198.500');
    expect(await salidasDe(datos.idSaga)).toBe(1);
  }, 40_000);
});
