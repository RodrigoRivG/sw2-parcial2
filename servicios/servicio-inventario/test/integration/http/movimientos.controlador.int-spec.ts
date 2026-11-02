import request from 'supertest';
import { AplicacionPrueba, PREFIJO, crearAplicacionPrueba, datosInsumo } from '../soporte/aplicacion-prueba';

describe('Movimientos (spec-movimientos.md)', () => {
  let ap: AplicacionPrueba;
  let admin: string;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
    admin = await ap.tokens.bearer(['administrador'], { sub: 'admin-1' });
  });

  afterAll(() => ap.cerrar());

  beforeEach(async () => {
    for (const coleccion of ['insumos', 'movimientos_inventario', 'registros_auditoria']) {
      await ap.conexion.collection(coleccion).deleteMany({});
    }
  });

  async function crearInsumo(cambios: Record<string, unknown> = {}): Promise<string> {
    const respuesta = await request(ap.servidor)
      .post(`${PREFIJO}/insumos`)
      .set('Authorization', admin)
      .send(datosInsumo(cambios));
    expect(respuesta.status).toBe(201);
    return respuesta.body.id;
  }

  const registrar = (cuerpo: Record<string, unknown>, autorizacion = admin) =>
    request(ap.servidor).post(`${PREFIJO}/movimientos`).set('Authorization', autorizacion).send(cuerpo);

  const stockDe = async (id: string) =>
    (await request(ap.servidor).get(`${PREFIJO}/insumos/${id}`).set('Authorization', admin)).body
      .stock;

  const contarMovimientos = () => ap.conexion.collection('movimientos_inventario').countDocuments();

  describe('Historia 1 — Registrar una entrada', () => {
    it('escenario 1: entrada de 80 sobre 120 → stock 200, costo vigente y auditoría', async () => {
      const id = await crearInsumo({ stockInicial: '120' });
      const respuesta = await registrar({
        idInsumo: id,
        tipo: 'ENTRADA',
        cantidad: '80',
        motivo: 'Compra factura 1234',
      }).set('X-Correlation-Id', 'corr-entrada');

      expect(respuesta.status).toBe(201);
      expect(respuesta.body).toEqual({
        id: expect.stringMatching(/^[0-9a-f-]{36}$/),
        idInsumo: id,
        tipo: 'ENTRADA',
        cantidad: '80.000',
        stockResultante: '200.000',
        costoUnitario: '4.8500',
        motivo: 'Compra factura 1234',
        actor: 'admin-1',
        idSaga: null,
        idLabor: null,
        fecha: expect.any(String),
      });
      expect(respuesta.headers.location).toBe(`${PREFIJO}/movimientos/${respuesta.body.id}`);
      expect(await stockDe(id)).toBe('200.000');
      const auditoria = await ap.conexion
        .collection('registros_auditoria')
        .findOne({ id_entidad: respuesta.body.id });
      expect(auditoria).toMatchObject({
        actor: 'admin-1',
        accion: 'REGISTRAR_MOVIMIENTO',
        entidad: 'MovimientoInventario',
        id_correlacion: 'corr-entrada',
      });
    });

    it('escenario 2: con UNIDAD, una entrada decimal → 422 CANTIDAD_INVALIDA', async () => {
      const id = await crearInsumo({ unidad: 'UNIDAD', nivelMinimo: '2' });
      const respuesta = await registrar({ idInsumo: id, tipo: 'ENTRADA', cantidad: '2.5', motivo: 'x' });
      expect([respuesta.status, respuesta.body.codigo]).toEqual([422, 'CANTIDAD_INVALIDA']);
    });

    it.each(['0', '-3'])('escenario 3: cantidad %s → 422 CANTIDAD_INVALIDA', async (cantidad) => {
      const id = await crearInsumo();
      const respuesta = await registrar({ idInsumo: id, tipo: 'ENTRADA', cantidad, motivo: 'x' });
      expect([respuesta.status, respuesta.body.codigo]).toEqual([422, 'CANTIDAD_INVALIDA']);
      expect(await contarMovimientos()).toBe(0);
    });

    it('escenario 4: insumo inexistente → 404 INSUMO_NO_ENCONTRADO', async () => {
      const respuesta = await registrar({
        idInsumo: '0b6f1c6e-2f7a-4a7e-9a39-7d5a1c2b3d4e',
        tipo: 'ENTRADA',
        cantidad: '1',
        motivo: 'x',
      });
      expect([respuesta.status, respuesta.body.codigo]).toEqual([404, 'INSUMO_NO_ENCONTRADO']);
    });
  });

  describe('Historia 2 — Registrar una salida manual', () => {
    it('escenarios 1 y 2: salidas de 30 y de todo el resto → 170 y luego 0', async () => {
      const id = await crearInsumo({ stockInicial: '200' });
      const primera = await registrar({ idInsumo: id, tipo: 'SALIDA', cantidad: '30', motivo: 'Bolsa rota' });
      expect([primera.status, primera.body.stockResultante]).toEqual([201, '170.000']);
      const segunda = await registrar({ idInsumo: id, tipo: 'SALIDA', cantidad: '170', motivo: 'Merma' });
      expect([segunda.status, segunda.body.stockResultante]).toEqual([201, '0.000']);
      expect(await stockDe(id)).toBe('0.000');
    });

    it('escenario 3: salida mayor al stock → 422 STOCK_INSUFICIENTE, sin cambios (RN-04)', async () => {
      const id = await crearInsumo({ stockInicial: '170' });
      const respuesta = await registrar({
        idInsumo: id,
        tipo: 'SALIDA',
        cantidad: '170.001',
        motivo: 'x',
      });
      expect(respuesta.status).toBe(422);
      expect(respuesta.body).toMatchObject({
        codigo: 'STOCK_INSUFICIENTE',
        detalles: [{ idInsumo: id, stockDisponible: '170.000', cantidadSolicitada: '170.001' }],
      });
      expect(await stockDe(id)).toBe('170.000');
      expect(await contarMovimientos()).toBe(1); // solo el stock inicial
    });

    it('escenario 4: gerencia y tecnico_campo no registran movimientos → 403', async () => {
      const id = await crearInsumo({ stockInicial: '10' });
      for (const rol of ['gerencia', 'tecnico_campo', 'lectura_inventario']) {
        const respuesta = await registrar(
          { idInsumo: id, tipo: 'SALIDA', cantidad: '1', motivo: 'x' },
          await ap.tokens.bearer([rol]),
        );
        expect([rol, respuesta.status, respuesta.body.codigo]).toEqual([rol, 403, 'SIN_PERMISO']);
      }
      expect(await stockDe(id)).toBe('10.000');
    });
  });

  describe('Historia 3 — Consultar movimientos', () => {
    const listar = (consulta: string, autorizacion = admin) =>
      request(ap.servidor).get(`${PREFIJO}/movimientos?${consulta}`).set('Authorization', autorizacion);

    it('escenario 1: 25 movimientos → los 20 más recientes por fecha descendente, con el total', async () => {
      const id = await crearInsumo({ stockInicial: '1' });
      for (let i = 1; i <= 24; i++) {
        await registrar({ idInsumo: id, tipo: 'ENTRADA', cantidad: String(i), motivo: `Entrada ${i}` });
      }
      const respuesta = await listar(`idInsumo=${id}`);
      expect(respuesta.status).toBe(200);
      expect(respuesta.body.total).toBe(25);
      expect(respuesta.body.items).toHaveLength(20);
      expect(respuesta.body.items[0].motivo).toBe('Entrada 24');
      const fechas = respuesta.body.items.map((m: { fecha: string }) => m.fecha);
      expect([...fechas].sort().reverse()).toEqual(fechas);
      // El último movimiento deja el stock actual (CE-MOV-02).
      expect(respuesta.body.items[0].stockResultante).toBe(await stockDe(id));
    });

    it('escenario 2: filtros por tipo y rango de fechas', async () => {
      const id = await crearInsumo({ stockInicial: '100' });
      await registrar({ idInsumo: id, tipo: 'SALIDA', cantidad: '5', motivo: 'Vieja' });
      const fechaCorte = new Date(Date.now() + 5);
      await new Promise((resolver) => setTimeout(resolver, 20));
      await registrar({ idInsumo: id, tipo: 'SALIDA', cantidad: '7', motivo: 'Nueva' });
      await registrar({ idInsumo: id, tipo: 'ENTRADA', cantidad: '1', motivo: 'Entrada nueva' });

      const salidas = await listar(`tipo=SALIDA&desde=${fechaCorte.toISOString()}`);
      expect(salidas.body.items.map((m: { motivo: string }) => m.motivo)).toEqual(['Nueva']);

      const hastaCorte = await listar(`hasta=${fechaCorte.toISOString()}`);
      expect(hastaCorte.body.items.map((m: { motivo: string }) => m.motivo).sort()).toEqual([
        'Stock inicial',
        'Vieja',
      ]);
    });

    it('escenario 3: filtro por idSaga', async () => {
      const id = await crearInsumo({ stockInicial: '10' });
      const idSaga = '5d7c2a1e-0b3f-4c55-9a1e-3f2b1c0d9e8a';
      // Los movimientos de la Saga llegan en spec-descuento-saga.md; aquí se marca uno a mano.
      await ap.conexion
        .collection('movimientos_inventario')
        .updateOne({ id_insumo: id }, { $set: { id_saga: idSaga, id_labor: 'labor-1' } });
      const respuesta = await listar(`idSaga=${idSaga}`);
      expect(respuesta.body.total).toBe(1);
      expect(respuesta.body.items[0]).toMatchObject({ idSaga, idLabor: 'labor-1' });
      expect((await listar('idSaga=0b6f1c6e-2f7a-4a7e-9a39-7d5a1c2b3d4e')).body.total).toBe(0);
    });

    it('escenario 5: detalle por ID e ID inexistente → 404 MOVIMIENTO_NO_ENCONTRADO', async () => {
      const id = await crearInsumo({ stockInicial: '10' });
      const [movimiento] = (await listar(`idInsumo=${id}`)).body.items;
      const detalle = await request(ap.servidor)
        .get(`${PREFIJO}/movimientos/${movimiento.id}`)
        .set('Authorization', await ap.tokens.bearer(['gerencia']));
      expect(detalle.body).toEqual(movimiento);

      const inexistente = await request(ap.servidor)
        .get(`${PREFIJO}/movimientos/0b6f1c6e-2f7a-4a7e-9a39-7d5a1c2b3d4e`)
        .set('Authorization', admin);
      expect([inexistente.status, inexistente.body.codigo]).toEqual([
        404,
        'MOVIMIENTO_NO_ENCONTRADO',
      ]);
    });

    it('lectura: gerencia sí; tecnico_campo y lectura_inventario no', async () => {
      expect((await listar('', await ap.tokens.bearer(['gerencia']))).status).toBe(200);
      for (const rol of ['tecnico_campo', 'lectura_inventario']) {
        expect((await listar('', await ap.tokens.bearer([rol]))).status).toBe(403);
      }
    });
  });

  describe('Casos borde', () => {
    it.each([
      ['motivo vacío', { motivo: '   ' }],
      ['motivo de 201 caracteres', { motivo: 'x'.repeat(201) }],
      ['cantidad con 4 decimales', { cantidad: '1.2345' }],
      ['cantidad como número JSON', { cantidad: 5 }],
      ['tipo desconocido', { tipo: 'AJUSTE' }],
      ['idSaga en un movimiento manual', { idSaga: '5d7c2a1e-0b3f-4c55-9a1e-3f2b1c0d9e8a' }],
      ['idLabor en un movimiento manual', { idLabor: 'labor-1' }],
      ['idInsumo que no es UUID', { idInsumo: 'urea' }],
    ])('%s → 400 DATOS_INVALIDOS', async (_caso, cambios) => {
      const id = await crearInsumo({ stockInicial: '10' });
      const respuesta = await registrar({
        idInsumo: id,
        tipo: 'ENTRADA',
        cantidad: '1',
        motivo: 'x',
        ...cambios,
      });
      expect([respuesta.status, respuesta.body.codigo]).toEqual([400, 'DATOS_INVALIDOS']);
      expect(await contarMovimientos()).toBe(1);
    });

    it('rango de fechas invertido → 400 DATOS_INVALIDOS', async () => {
      const respuesta = await request(ap.servidor)
        .get(`${PREFIJO}/movimientos?desde=2026-11-10T00:00:00Z&hasta=2026-11-01T00:00:00Z`)
        .set('Authorization', admin);
      expect(respuesta.status).toBe(400);
      expect(respuesta.body).toMatchObject({
        codigo: 'DATOS_INVALIDOS',
        detalles: [{ campo: 'desde' }],
      });
    });

    it('fecha mal formada → 400 DATOS_INVALIDOS', async () => {
      const respuesta = await request(ap.servidor)
        .get(`${PREFIJO}/movimientos?desde=ayer`)
        .set('Authorization', admin);
      expect([respuesta.status, respuesta.body.codigo]).toEqual([400, 'DATOS_INVALIDOS']);
    });

    it.each(['put', 'delete', 'patch'] as const)(
      '%s sobre un movimiento → 404 RECURSO_NO_ENCONTRADO (son inmutables)',
      async (metodo) => {
        const cliente = request(ap.servidor);
        const respuesta = await cliente[metodo](
          `${PREFIJO}/movimientos/0b6f1c6e-2f7a-4a7e-9a39-7d5a1c2b3d4e`,
        )
          .set('Authorization', admin)
          .send({});
        expect([respuesta.status, respuesta.body.codigo]).toEqual([404, 'RECURSO_NO_ENCONTRADO']);
      },
    );
  });
});
