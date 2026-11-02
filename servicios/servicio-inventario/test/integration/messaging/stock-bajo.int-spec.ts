import request from 'supertest';
import { EvaluacionStockBajo } from '../../../src/adapters/inbound/evaluacion-stock-bajo';
import { RelojSistema } from '../../../src/adapters/outbound/reloj-sistema';
import { VENTANA_ALERTA_MS } from '../../../src/domain/supply/politica-stock-bajo';
import {
  AplicacionPrueba,
  PREFIJO,
  RelojPrueba,
  crearAplicacionPrueba,
  datosInsumo,
} from '../soporte/aplicacion-prueba';
import { OyenteEventos } from '../soporte/oyente-eventos';

const HORA = 60 * 60 * 1000;

describe('Evento de stock bajo (spec-stock-bajo.md, RN-05)', () => {
  let ap: AplicacionPrueba;
  let oyente: OyenteEventos;
  let admin: string;
  const reloj = new RelojPrueba();

  beforeAll(async () => {
    ap = await crearAplicacionPrueba((c) => c.overrideProvider(RelojSistema).useValue(reloj));
    oyente = await OyenteEventos.escuchar('inventario.stock.bajo');
    admin = await ap.tokens.bearer(['administrador']);
  });

  afterAll(async () => {
    await oyente.cerrar();
    await ap.cerrar();
  });

  beforeEach(async () => {
    reloj.instante = new Date('2026-11-02T10:00:00Z');
    for (const coleccion of ['insumos', 'movimientos_inventario', 'registros_auditoria']) {
      await ap.conexion.collection(coleccion).deleteMany({});
    }
    oyente.vaciar();
  });

  async function crearInsumo(nombre: string, stock: string, minimo: string): Promise<string> {
    const respuesta = await request(ap.servidor)
      .post(`${PREFIJO}/insumos`)
      .set('Authorization', admin)
      .send(datosInsumo({ nombre, stockInicial: stock, nivelMinimo: minimo }));
    expect(respuesta.status).toBe(201);
    return respuesta.body.id;
  }

  async function mover(idInsumo: string, tipo: string, cantidad: string, idCorrelacion?: string) {
    const solicitud = request(ap.servidor)
      .post(`${PREFIJO}/movimientos`)
      .set('Authorization', admin);
    if (idCorrelacion) {
      solicitud.set('X-Correlation-Id', idCorrelacion);
    }
    const respuesta = await solicitud.send({ idInsumo, tipo, cantidad, motivo: 'Prueba' });
    expect(respuesta.status).toBe(201);
    return respuesta;
  }

  /** Espera a que terminen las evaluaciones y devuelve los eventos del insumo. */
  async function eventosDe(idInsumo: string, esperados: number) {
    await ap.app.get(EvaluacionStockBajo).esperarPendientes();
    const recibidos = await oyente.esperar(esperados, esperados === 0 ? 500 : 5000);
    return recibidos.filter((e) => e.datos.idInsumo === idInsumo);
  }

  const fechaUltimaAlerta = async (id: string) =>
    (await ap.conexion.collection('insumos').findOne({ _id: id as never }))?.fecha_ultima_alerta;

  describe('Historia 1 — Avisar cuando un insumo llega al nivel mínimo', () => {
    it('escenarios 1 y 5: salida que deja el stock en el mínimo → evento StockBajo con el sobre común', async () => {
      const id = await crearInsumo('Urea', '60', '50');
      await mover(id, 'SALIDA', '10', 'corr-stock-bajo');

      const [evento, ...otros] = await eventosDe(id, 1);
      expect(otros).toHaveLength(0);
      expect(evento).toEqual({
        idMensaje: expect.stringMatching(/^[0-9a-f-]{36}$/),
        idCorrelacion: 'corr-stock-bajo',
        tipo: 'StockBajo',
        version: 1,
        fechaOcurrencia: '2026-11-02T10:00:00.000Z',
        origen: 'servicio-inventario',
        datos: { idInsumo: id, nombre: 'Urea', stock: '50.000', nivelMinimo: '50.000', unidad: 'KILOGRAMO' },
      });
      expect(await fechaUltimaAlerta(id)).toEqual(new Date('2026-11-02T10:00:00Z'));
    });

    it('escenario 2: salida que deja el stock por encima del mínimo → no hay evento', async () => {
      const id = await crearInsumo('Urea', '80', '50');
      await mover(id, 'SALIDA', '10');
      expect(await eventosDe(id, 0)).toEqual([]);
      expect(await fechaUltimaAlerta(id)).toBeNull();
    });

    it('escenario 3: varios insumos afectados a la vez → un evento por cada uno', async () => {
      const urea = await crearInsumo('Urea', '60', '50');
      const glifosato = await crearInsumo('Glifosato', '30', '20');
      expect(await eventosDe(urea, 0)).toEqual([]);
      // Simula el descuento de la Saga, que deja ambos bajo el mínimo y entrega los dos insumos
      // juntos (spec-descuento-saga.md).
      await ap.conexion.collection('insumos').updateMany({}, [
        { $set: { stock: { $toDecimal: '5' } } },
      ]);
      ap.app.get(EvaluacionStockBajo).programar([urea, glifosato]);
      await ap.app.get(EvaluacionStockBajo).esperarPendientes();
      const recibidos = await oyente.esperar(2);
      expect(recibidos.map((e) => e.datos.nombre).sort()).toEqual(['Glifosato', 'Urea']);
    });

    it('escenario 4: una entrada que deja el stock todavía bajo el mínimo también alerta', async () => {
      const id = await crearInsumo('Urea', '10', '50');
      expect(await eventosDe(id, 1)).toHaveLength(1); // el stock inicial ya es un movimiento
      reloj.avanzar(VENTANA_ALERTA_MS);
      oyente.vaciar();
      await mover(id, 'ENTRADA', '5');
      const [evento] = await eventosDe(id, 1);
      expect(evento.datos.stock).toBe('15.000');
    });

    it('crear un insumo sin stock inicial no alerta (no hubo movimiento)', async () => {
      const id = await crearInsumo('Urea', '0', '50');
      expect(await eventosDe(id, 0)).toEqual([]);
    });
  });

  describe('Historia 2 — No repetir la alerta más de una vez cada 24 horas', () => {
    it('escenarios 1 y 2: a las 15:00 no; al día siguiente a las 10:00 (24 h exactas) sí', async () => {
      const id = await crearInsumo('Urea', '60', '50');
      await mover(id, 'SALIDA', '10');
      expect(await eventosDe(id, 1)).toHaveLength(1);

      reloj.avanzar(5 * HORA);
      oyente.vaciar();
      await mover(id, 'SALIDA', '10');
      expect(await eventosDe(id, 0)).toEqual([]);

      reloj.avanzar(19 * HORA);
      await mover(id, 'SALIDA', '10');
      const [evento] = await eventosDe(id, 1);
      expect(evento.datos.stock).toBe('30.000');
      expect(await fechaUltimaAlerta(id)).toEqual(new Date('2026-11-03T10:00:00Z'));
    });

    it('escenario 3: reponer por encima del mínimo no reinicia la ventana de 24 h', async () => {
      const id = await crearInsumo('Urea', '60', '50');
      await mover(id, 'SALIDA', '10');
      expect(await eventosDe(id, 1)).toHaveLength(1);
      reloj.avanzar(HORA);
      await mover(id, 'ENTRADA', '100');
      reloj.avanzar(3 * HORA);
      oyente.vaciar();
      await mover(id, 'SALIDA', '110');
      expect(await eventosDe(id, 0)).toEqual([]);
    });
  });

  describe('Casos borde', () => {
    it('cambiar el nivel mínimo con PUT no publica, aunque el stock quede bajo el nuevo mínimo', async () => {
      const id = await crearInsumo('Urea', '80', '50');
      expect(await eventosDe(id, 0)).toEqual([]);
      const respuesta = await request(ap.servidor)
        .put(`${PREFIJO}/insumos/${id}`)
        .set('Authorization', admin)
        .send(datosInsumo({ nombre: 'Urea', nivelMinimo: '100', version: 0 }));
      expect([respuesta.status, respuesta.body.stockBajo]).toEqual([200, true]);
      expect(await eventosDe(id, 0)).toEqual([]);
    });

    it('un movimiento rechazado no evalúa la regla', async () => {
      const id = await crearInsumo('Urea', '60', '50');
      const rechazado = await request(ap.servidor)
        .post(`${PREFIJO}/movimientos`)
        .set('Authorization', admin)
        .send({ idInsumo: id, tipo: 'SALIDA', cantidad: '61', motivo: 'x' });
      expect(rechazado.status).toBe(422);
      expect(await eventosDe(id, 0)).toEqual([]);
    });

    it('una reserva vencida (proceso caído antes de publicar) no bloquea la alerta', async () => {
      const id = await crearInsumo('Urea', '60', '50');
      await ap.conexion
        .collection('insumos')
        .updateOne({ _id: id as never }, { $set: { reserva_alerta_hasta: new Date('2026-11-02T09:59:00Z') } });
      await mover(id, 'SALIDA', '10');
      expect(await eventosDe(id, 1)).toHaveLength(1);
    });
  });
});
