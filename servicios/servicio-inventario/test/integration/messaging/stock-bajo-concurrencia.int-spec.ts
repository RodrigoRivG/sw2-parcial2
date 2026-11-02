import request from 'supertest';
import { EvaluacionStockBajo } from '../../../src/adapters/inbound/evaluacion-stock-bajo';
import { AplicacionPrueba, PREFIJO, crearAplicacionPrueba, datosInsumo } from '../soporte/aplicacion-prueba';
import { OyenteEventos } from '../soporte/oyente-eventos';

describe('Stock bajo con movimientos simultáneos (CE-SBJ-02)', () => {
  let ap: AplicacionPrueba;
  let oyente: OyenteEventos;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
    oyente = await OyenteEventos.escuchar('inventario.stock.bajo');
  });

  afterAll(async () => {
    await oyente.cerrar();
    await ap.cerrar();
  });

  it('20 salidas simultáneas que dejan el insumo bajo el mínimo → un solo evento', async () => {
    const admin = await ap.tokens.bearer(['administrador']);
    const creado = await request(ap.servidor)
      .post(`${PREFIJO}/insumos`)
      .set('Authorization', admin)
      .send(datosInsumo({ stockInicial: '100', nivelMinimo: '95' }));
    const id = creado.body.id;

    const respuestas = await Promise.all(
      Array.from({ length: 20 }, () =>
        request(ap.servidor)
          .post(`${PREFIJO}/movimientos`)
          .set('Authorization', admin)
          .send({ idInsumo: id, tipo: 'SALIDA', cantidad: '1', motivo: 'Consumo' }),
      ),
    );
    expect(respuestas.every((r) => r.status === 201)).toBe(true);

    await ap.app.get(EvaluacionStockBajo).esperarPendientes();
    const recibidos = await oyente.esperar(2, 1500);
    expect(recibidos.filter((e) => e.datos.idInsumo === id)).toHaveLength(1);
    const insumo = await ap.conexion.collection('insumos').findOne({ _id: id });
    expect(insumo?.fecha_ultima_alerta).toBeInstanceOf(Date);
    expect(insumo?.reserva_alerta_hasta).toBeNull();
  });
});
