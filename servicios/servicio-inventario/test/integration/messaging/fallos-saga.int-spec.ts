import { randomUUID } from 'node:crypto';
import { Connection } from 'mongoose';
import { CONEXION_MONGO } from '../../../src/adapters/outbound/persistence/conexion-mongo';
import { RepositorioSagaProcesadaMongo } from '../../../src/adapters/outbound/persistence/repositorio-saga-procesada.mongo';
import { esquemaSagaProcesada } from '../../../src/adapters/outbound/persistence/schemas/saga-procesada.esquema';
import { SagaProcesada } from '../../../src/domain/saga/saga-procesada.entidad';
import {
  AplicacionPrueba,
  crearAplicacionPrueba,
  crearInsumoApi,
  stockDe,
} from '../soporte/aplicacion-prueba';
import { ClienteSaga } from '../soporte/cliente-saga';

/** El repositorio real, que falla a pedido del test simulando una base de datos caída. */
class RepositorioConFallas extends RepositorioSagaProcesadaMongo {
  fallar = false;
  llamadas = 0;

  override obtenerParaProcesar(idSaga: string, idLabor: string, ahora: Date): Promise<SagaProcesada> {
    if (this.fallar) {
      this.llamadas++;
      return Promise.reject(new Error('MongoDB no responde'));
    }
    return super.obtenerParaProcesar(idSaga, idLabor, ahora);
  }
}

describe('Fallos técnicos y mensajes inválidos (Historia 4, RNF-11)', () => {
  let ap: AplicacionPrueba;
  let saga: ClienteSaga;
  let repositorio: RepositorioConFallas;
  let urea: string;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba((c) =>
      c.overrideProvider(RepositorioSagaProcesadaMongo).useFactory({
        factory: (conexion: Connection) =>
          (repositorio = new RepositorioConFallas(conexion.model('SagaProcesada', esquemaSagaProcesada))),
        inject: [CONEXION_MONGO],
      }),
    );
    saga = await ClienteSaga.conectar();
    urea = await crearInsumoApi(ap, { nombre: 'Urea', stockInicial: '200' });
  });

  afterAll(async () => {
    await saga.cerrar();
    await ap.cerrar();
  });

  beforeEach(() => {
    repositorio.fallar = false;
    repositorio.llamadas = 0;
  });

  it('escenario 1: con la base caída → 1 intento + 3 reintentos, DLQ y ninguna respuesta', async () => {
    repositorio.fallar = true;
    const idSaga = randomUUID();
    saga.enviar('DescontarInsumos', { idSaga, idLabor: randomUUID(), items: [{ idInsumo: urea, cantidad: '1' }] });
    const [enDlq] = await saga.leerDlq(1);
    expect(JSON.parse(enDlq)).toMatchObject({ idCorrelacion: idSaga, tipo: 'DescontarInsumos' });
    expect(repositorio.llamadas).toBe(4);
    expect(await saga.esperarRespuestas(idSaga, 1, 500)).toHaveLength(0);
    expect(await stockDe(ap, urea)).toBe('200.000');
  });

  it('un fallo pasajero se recupera con un reintento y responde una sola vez', async () => {
    repositorio.fallar = true;
    const idSaga = randomUUID();
    saga.enviar('DescontarInsumos', { idSaga, idLabor: randomUUID(), items: [{ idInsumo: urea, cantidad: '1' }] });
    await new Promise((resolver) => setTimeout(resolver, 15));
    repositorio.fallar = false;
    const respuestas = await saga.esperarRespuestas(idSaga, 2, 1500);
    expect(respuestas.map((r) => r.tipo)).toEqual(['InsumosDescontados']);
    expect(await saga.leerDlq(1, 300)).toHaveLength(0);
    expect(await stockDe(ap, urea)).toBe('199.000');
  });

  it.each([
    ['JSON inválido', '{"idMensaje": '],
    ['sin idCorrelacion', JSON.stringify({ idMensaje: randomUUID(), tipo: 'DescontarInsumos', datos: {} })],
    ['tipo desconocido', JSON.stringify({ idMensaje: randomUUID(), idCorrelacion: randomUUID(), tipo: 'BorrarTodo', datos: {} })],
  ])('escenario 2: %s → DLQ sin reintentos ni respuesta', async (_caso, contenido) => {
    saga.enviarCrudo(contenido);
    expect(await saga.leerDlq(1)).toEqual([contenido]);
    expect(repositorio.llamadas).toBe(0);
  });

  it('RestaurarInsumos sin un idSaga válido → DLQ (no hay a quién responder)', async () => {
    const idCorrelacion = randomUUID();
    saga.enviar('RestaurarInsumos', { idSaga: 'S1', idLabor: randomUUID() }, { idCorrelacion });
    const [enDlq] = await saga.leerDlq(1);
    expect(JSON.parse(enDlq)).toMatchObject({ idCorrelacion, tipo: 'RestaurarInsumos' });
    expect(await saga.esperarRespuestas(idCorrelacion, 1, 300)).toHaveLength(0);
  });

  it.each([
    ['cantidad como número JSON', { cantidad: 5 }, {}],
    ['cantidad 0', { cantidad: '0' }, {}],
    ['versión 2', {}, { version: 2 }],
  ])('escenario 3: %s → InsumosRechazados con DATOS_INVALIDOS (no va a la DLQ)', async (_caso, cambioItem, opciones) => {
    const idSaga = randomUUID();
    saga.enviar(
      'DescontarInsumos',
      { idSaga, idLabor: randomUUID(), items: [{ idInsumo: urea, cantidad: '1', ...cambioItem }] },
      opciones,
    );
    const respuesta = await saga.esperarRespuesta(idSaga);
    expect([respuesta.tipo, respuesta.datos.codigo]).toEqual(['InsumosRechazados', 'DATOS_INVALIDOS']);
    expect(await saga.leerDlq(1, 300)).toHaveLength(0);
  });

  it('idCorrelacion distinto de idSaga → DATOS_INVALIDOS con el idCorrelacion del comando', async () => {
    const idCorrelacion = randomUUID();
    const idSaga = randomUUID();
    saga.enviar(
      'DescontarInsumos',
      { idSaga, idLabor: randomUUID(), items: [{ idInsumo: urea, cantidad: '1' }] },
      { idCorrelacion },
    );
    const respuesta = await saga.esperarRespuesta(idCorrelacion);
    expect(respuesta.datos).toMatchObject({ idSaga, codigo: 'DATOS_INVALIDOS' });
  });
});
