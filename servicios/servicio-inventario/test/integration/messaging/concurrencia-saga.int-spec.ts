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

describe('Concurrencia de la Saga (constitución §6, CE-SAG-02)', () => {
  let ap: AplicacionPrueba;
  let saga: ClienteSaga;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
    saga = await ClienteSaga.conectar();
  });

  afterAll(async () => {
    await saga.cerrar();
    await ap.cerrar();
  });

  it('dos Sagas sobre un insumo con stock para una sola → una descontada, otra STOCK_INSUFICIENTE', async () => {
    for (let ronda = 0; ronda < 5; ronda++) {
      const insumo = await crearInsumoApi(ap, { nombre: `Fungicida ${ronda}`, stockInicial: '10' });
      const sagas = [randomUUID(), randomUUID()];
      for (const idSaga of sagas) {
        saga.enviar('DescontarInsumos', {
          idSaga,
          idLabor: randomUUID(),
          items: [{ idInsumo: insumo, cantidad: '10' }],
        });
      }
      const respuestas = await Promise.all(sagas.map((idSaga) => saga.esperarRespuesta(idSaga)));
      expect(respuestas.map((r) => r.tipo).sort()).toEqual(['InsumosDescontados', 'InsumosRechazados']);
      expect(respuestas.find((r) => r.tipo === 'InsumosRechazados')?.datos.codigo).toBe('STOCK_INSUFICIENTE');
      expect(await stockDe(ap, insumo)).toBe('0.000');
    }
  });

  it('una Saga y una salida manual simultáneas nunca dejan stock negativo', async () => {
    const admin = await ap.tokens.bearer(['administrador']);
    for (let ronda = 0; ronda < 5; ronda++) {
      const insumo = await crearInsumoApi(ap, { nombre: `Herbicida ${ronda}`, stockInicial: '10' });
      const idSaga = randomUUID();
      saga.enviar('DescontarInsumos', {
        idSaga,
        idLabor: randomUUID(),
        items: [{ idInsumo: insumo, cantidad: '10' }],
      });
      const [manual, respuesta] = await Promise.all([
        request(ap.servidor)
          .post(`${PREFIJO}/movimientos`)
          .set('Authorization', admin)
          .send({ idInsumo: insumo, tipo: 'SALIDA', cantidad: '10', motivo: 'Merma' }),
        saga.esperarRespuesta(idSaga),
      ]);
      const ganadores = [manual.status === 201, respuesta.tipo === 'InsumosDescontados'];
      expect(ganadores.filter(Boolean)).toHaveLength(1);
      if (manual.status !== 201) {
        expect([manual.status, manual.body.codigo]).toEqual([422, 'STOCK_INSUFICIENTE']);
      }
      expect(await stockDe(ap, insumo)).toBe('0.000');
    }
  });
});
