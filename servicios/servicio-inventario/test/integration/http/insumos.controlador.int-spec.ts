import request from 'supertest';
import { AplicacionPrueba, PREFIJO, crearAplicacionPrueba, datosInsumo } from '../soporte/aplicacion-prueba';

describe('Insumos (spec-insumos.md)', () => {
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

  const registrarMovimiento = (idInsumo: string, tipo: string, cantidad: string) =>
    request(ap.servidor)
      .post(`${PREFIJO}/movimientos`)
      .set('Authorization', admin)
      .send({ idInsumo, tipo, cantidad, motivo: 'Prueba' });

  const crear = (cuerpo: Record<string, unknown>, autorizacion = admin) =>
    request(ap.servidor).post(`${PREFIJO}/insumos`).set('Authorization', autorizacion).send(cuerpo);

  const auditorias = () => ap.conexion.collection('registros_auditoria').find({}).toArray();

  describe('Historia 1 — Registrar un insumo', () => {
    it('escenario 1: con stock inicial se crea con ese stock y una ENTRADA "Stock inicial"', async () => {
      const respuesta = await crear(datosInsumo({ stockInicial: '500' }));
      expect(respuesta.status).toBe(201);
      expect(respuesta.body.stock).toBe('500.000');
      expect(respuesta.body.stockBajo).toBe(false);

      const movimientos = await ap.conexion
        .collection('movimientos_inventario')
        .find({ id_insumo: respuesta.body.id })
        .toArray();
      expect(movimientos).toHaveLength(1);
      expect(movimientos[0]).toMatchObject({ tipo: 'ENTRADA', motivo: 'Stock inicial', actor: 'admin-1' });
      expect(movimientos[0].cantidad.toString()).toBe('500');
      expect(movimientos[0].stock_resultante.toString()).toBe('500');
      expect((await auditorias()).map((a) => a.accion)).toEqual(['CREAR', 'REGISTRAR_MOVIMIENTO']);
    });

    it('si el insumo no se puede crear, tampoco queda el movimiento del stock inicial', async () => {
      expect((await crear(datosInsumo({ stockInicial: '10' }))).status).toBe(201);
      const repetido = await crear(datosInsumo({ nombre: 'UREA 46 %', stockInicial: '10' }));
      expect(repetido.status).toBe(409);
      expect(await ap.conexion.collection('movimientos_inventario').countDocuments()).toBe(1);
    });

    it('escenario 2: sin stock inicial se crea con stock 0, Location y auditoría CREAR', async () => {
      const respuesta = await crear(datosInsumo({ stockInicial: '0' })).set(
        'X-Correlation-Id',
        'corr-crear-1',
      );

      expect(respuesta.status).toBe(201);
      expect(respuesta.body).toEqual({
        id: expect.stringMatching(/^[0-9a-f-]{36}$/),
        nombre: 'Urea 46 %',
        categoria: 'FERTILIZANTE',
        unidad: 'KILOGRAMO',
        stock: '0.000',
        nivelMinimo: '50.000',
        costoUnitario: '4.8500',
        descripcion: 'Bolsa de 50 kg',
        stockBajo: true,
        version: 0,
        fechaCreacion: expect.any(String),
        fechaActualizacion: expect.any(String),
      });
      expect(respuesta.headers.location).toBe(`${PREFIJO}/insumos/${respuesta.body.id}`);
      expect(await auditorias()).toEqual([
        expect.objectContaining({
          actor: 'admin-1',
          accion: 'CREAR',
          entidad: 'Insumo',
          id_entidad: respuesta.body.id,
          id_correlacion: 'corr-crear-1',
        }),
      ]);
    });

    it('escenario 3: con UNIDAD, stock inicial o nivel mínimo decimal → 422 CANTIDAD_INVALIDA', async () => {
      const unidad = { unidad: 'UNIDAD', nombre: 'Trampa' };
      const r1 = await crear(datosInsumo({ ...unidad, stockInicial: '10.5', nivelMinimo: '2' }));
      const r2 = await crear(datosInsumo({ ...unidad, nivelMinimo: '2.5' }));
      expect([r1.status, r1.body.codigo]).toEqual([422, 'CANTIDAD_INVALIDA']);
      expect([r2.status, r2.body.codigo]).toEqual([422, 'CANTIDAD_INVALIDA']);
      expect(await ap.conexion.collection('insumos').countDocuments()).toBe(0);
      expect(await auditorias()).toHaveLength(0);
    });

    it('escenario 4: costo negativo → 422 COSTO_UNITARIO_INVALIDO; costo 0 se acepta', async () => {
      const negativo = await crear(datosInsumo({ costoUnitario: '-1' }));
      expect([negativo.status, negativo.body.codigo]).toEqual([422, 'COSTO_UNITARIO_INVALIDO']);
      const donado = await crear(datosInsumo({ costoUnitario: '0' }));
      expect(donado.status).toBe(201);
      expect(donado.body.costoUnitario).toBe('0.0000');
    });

    it('escenario 5: nombre repetido sin distinguir mayúsculas → 409 NOMBRE_INSUMO_DUPLICADO', async () => {
      expect((await crear(datosInsumo())).status).toBe(201);
      const repetido = await crear(datosInsumo({ nombre: 'urea 46 %' }));
      expect([repetido.status, repetido.body.codigo]).toEqual([409, 'NOMBRE_INSUMO_DUPLICADO']);
      expect(await auditorias()).toHaveLength(1);
    });

    it('escenario 6: gerencia y tecnico_campo no pueden registrar → 403 SIN_PERMISO', async () => {
      for (const rol of ['gerencia', 'tecnico_campo', 'lectura_inventario']) {
        const respuesta = await crear(datosInsumo(), await ap.tokens.bearer([rol]));
        expect([rol, respuesta.status, respuesta.body.codigo]).toEqual([rol, 403, 'SIN_PERMISO']);
      }
      expect(await ap.conexion.collection('insumos').countDocuments()).toBe(0);
    });
  });

  describe('Historia 2 — Consultar insumos', () => {
    it('escenario 1: 30 insumos → los 20 primeros por nombre, con el total', async () => {
      for (let i = 30; i >= 1; i--) {
        await crear(datosInsumo({ nombre: `Insumo ${String(i).padStart(2, '0')}` }));
      }
      const respuesta = await request(ap.servidor)
        .get(`${PREFIJO}/insumos`)
        .set('Authorization', admin);
      expect(respuesta.status).toBe(200);
      expect(respuesta.body.total).toBe(30);
      expect(respuesta.body.pagina).toBe(0);
      expect(respuesta.body.tamanio).toBe(20);
      expect(respuesta.body.items).toHaveLength(20);
      expect(respuesta.body.items[0].nombre).toBe('Insumo 01');
      expect(respuesta.body.items[19].nombre).toBe('Insumo 20');

      const segunda = await request(ap.servidor)
        .get(`${PREFIJO}/insumos?pagina=1&tamanio=20`)
        .set('Authorization', admin);
      expect(segunda.body.items.map((i: { nombre: string }) => i.nombre)).toEqual(
        Array.from({ length: 10 }, (_, k) => `Insumo ${21 + k}`),
      );
    });

    it('escenario 2: filtros por categoría y texto del nombre sin distinguir mayúsculas', async () => {
      await crear(datosInsumo({ nombre: 'Semilla de Maiz DK-7088', categoria: 'SEMILLA' }));
      await crear(datosInsumo({ nombre: 'Semilla de soja', categoria: 'SEMILLA' }));
      await crear(datosInsumo({ nombre: 'Maiz molido (abono)', categoria: 'FERTILIZANTE' }));
      const respuesta = await request(ap.servidor)
        .get(`${PREFIJO}/insumos?categoria=SEMILLA&nombre=maiz`)
        .set('Authorization', admin);
      expect(respuesta.body.items.map((i: { nombre: string }) => i.nombre)).toEqual([
        'Semilla de Maiz DK-7088',
      ]);
      expect(respuesta.body.total).toBe(1);

      const conSimbolos = await request(ap.servidor)
        .get(`${PREFIJO}/insumos?nombre=${encodeURIComponent('(abono)')}`)
        .set('Authorization', admin);
      expect(conSimbolos.body.total).toBe(1);
    });

    it('escenario 3: soloConStock=true devuelve solo insumos con stock mayor a 0', async () => {
      await crear(datosInsumo({ nombre: 'Con stock', stockInicial: '5' }));
      await crear(datosInsumo({ nombre: 'Sin stock' }));
      const agotado = await crear(datosInsumo({ nombre: 'Agotado', stockInicial: '3' }));
      expect((await registrarMovimiento(agotado.body.id, 'SALIDA', '3')).status).toBe(201);

      const respuesta = await request(ap.servidor)
        .get(`${PREFIJO}/insumos?soloConStock=true`)
        .set('Authorization', admin);
      expect(respuesta.body.items).toEqual([
        expect.objectContaining({ nombre: 'Con stock', stock: '5.000' }),
      ]);
    });

    it('escenario 7: ID inexistente → 404 INSUMO_NO_ENCONTRADO', async () => {
      const respuesta = await request(ap.servidor)
        .get(`${PREFIJO}/insumos/0b6f1c6e-2f7a-4a7e-9a39-7d5a1c2b3d4e`)
        .set('Authorization', admin);
      expect([respuesta.status, respuesta.body.codigo]).toEqual([404, 'INSUMO_NO_ENCONTRADO']);
    });
  });

  describe('Historia 3 — Modificar un insumo', () => {
    const actualizar = (id: string, cuerpo: Record<string, unknown>) =>
      request(ap.servidor).put(`${PREFIJO}/insumos/${id}`).set('Authorization', admin).send(cuerpo);

    it('escenario 1: cambia el costo, incrementa la versión y audita MODIFICAR', async () => {
      const creado = await crear(datosInsumo());
      const respuesta = await actualizar(
        creado.body.id,
        datosInsumo({ costoUnitario: '5.10', version: 0 }),
      );
      expect(respuesta.status).toBe(200);
      expect(respuesta.body.costoUnitario).toBe('5.1000');
      expect(respuesta.body.version).toBe(1);
      expect((await auditorias()).map((a) => a.accion)).toEqual(['CREAR', 'MODIFICAR']);
    });

    it('escenario 2: sin movimientos se puede cambiar la unidad', async () => {
      const creado = await crear(datosInsumo());
      const respuesta = await actualizar(creado.body.id, datosInsumo({ unidad: 'LITRO', version: 0 }));
      expect([respuesta.status, respuesta.body.unidad]).toEqual([200, 'LITRO']);
    });

    it('escenario 3: con movimientos, cambiar la unidad → 422 UNIDAD_NO_MODIFICABLE', async () => {
      const creado = await crear(datosInsumo());
      expect((await registrarMovimiento(creado.body.id, 'ENTRADA', '1')).status).toBe(201);
      const respuesta = await actualizar(creado.body.id, datosInsumo({ unidad: 'LITRO', version: 0 }));
      expect([respuesta.status, respuesta.body.codigo]).toEqual([422, 'UNIDAD_NO_MODIFICABLE']);
    });

    it('escenario 4: versión anterior → 409 CONFLICTO_CONCURRENCIA', async () => {
      const creado = await crear(datosInsumo());
      expect((await actualizar(creado.body.id, datosInsumo({ version: 0 }))).status).toBe(200);
      const respuesta = await actualizar(creado.body.id, datosInsumo({ version: 0 }));
      expect([respuesta.status, respuesta.body.codigo]).toEqual([409, 'CONFLICTO_CONCURRENCIA']);
    });

    it('escenario 5: un cambio de stock entre la lectura y el PUT no invalida la versión', async () => {
      const creado = await crear(datosInsumo({ stockInicial: '20' }));
      // Una salida entre la lectura (versión 0) y el PUT no cambia la versión (README D-05).
      expect((await registrarMovimiento(creado.body.id, 'SALIDA', '10')).status).toBe(201);
      const respuesta = await actualizar(creado.body.id, datosInsumo({ nombre: 'Urea', version: 0 }));
      expect(respuesta.status).toBe(200);
      expect(respuesta.body.stock).toBe('10.000');
      expect(respuesta.body.version).toBe(1);
    });

    it('escenario 6: el stock no se modifica por PUT → 400 DATOS_INVALIDOS', async () => {
      const creado = await crear(datosInsumo());
      const respuesta = await actualizar(
        creado.body.id,
        datosInsumo({ stock: '999', version: 0 }),
      );
      expect([respuesta.status, respuesta.body.codigo]).toEqual([400, 'DATOS_INVALIDOS']);
    });

    it('renombrar con el nombre de otro insumo → 409 NOMBRE_INSUMO_DUPLICADO', async () => {
      await crear(datosInsumo({ nombre: 'Glifosato' }));
      const creado = await crear(datosInsumo());
      const respuesta = await actualizar(
        creado.body.id,
        datosInsumo({ nombre: 'GLIFOSATO', version: 0 }),
      );
      expect([respuesta.status, respuesta.body.codigo]).toEqual([409, 'NOMBRE_INSUMO_DUPLICADO']);
    });

    it('un insumo inexistente → 404 INSUMO_NO_ENCONTRADO', async () => {
      const respuesta = await actualizar(
        '0b6f1c6e-2f7a-4a7e-9a39-7d5a1c2b3d4e',
        datosInsumo({ version: 0 }),
      );
      expect([respuesta.status, respuesta.body.codigo]).toEqual([404, 'INSUMO_NO_ENCONTRADO']);
    });
  });

  describe('Casos borde', () => {
    it.each([
      ['stock inicial con 4 decimales', { stockInicial: '1.2345' }],
      ['costo con 5 decimales', { costoUnitario: '1.23456' }],
      ['nivel mínimo como número JSON', { nivelMinimo: 50 }],
      ['costo como número JSON', { costoUnitario: 4.85 }],
      ['categoría desconocida', { categoria: 'HERBICIDA' }],
      ['nombre vacío', { nombre: '   ' }],
      ['nombre de 101 caracteres', { nombre: 'x'.repeat(101) }],
      ['campo no permitido', { proveedor: 'ACME' }],
    ])('%s → 400 DATOS_INVALIDOS con detalle por campo', async (_caso, cambios) => {
      const respuesta = await crear(datosInsumo(cambios));
      expect(respuesta.status).toBe(400);
      expect(respuesta.body).toMatchObject({ codigo: 'DATOS_INVALIDOS' });
      expect(respuesta.body.detalles.length).toBeGreaterThan(0);
    });

    it('nivel mínimo negativo → 422 NIVEL_MINIMO_INVALIDO; stock inicial negativo → 422 CANTIDAD_INVALIDA', async () => {
      const nivel = await crear(datosInsumo({ nivelMinimo: '-1' }));
      const stock = await crear(datosInsumo({ stockInicial: '-5' }));
      expect([nivel.status, nivel.body.codigo]).toEqual([422, 'NIVEL_MINIMO_INVALIDO']);
      expect([stock.status, stock.body.codigo]).toEqual([422, 'CANTIDAD_INVALIDA']);
    });

    it('el nombre se recorta antes de validar la unicidad', async () => {
      const creado = await crear(datosInsumo({ nombre: '  Urea 46 %  ' }));
      expect(creado.body.nombre).toBe('Urea 46 %');
      const repetido = await crear(datosInsumo({ nombre: 'UREA 46 %   ' }));
      expect(repetido.status).toBe(409);
    });

    it('cambiar la unidad a UNIDAD con un nivel mínimo decimal → 422 CANTIDAD_INVALIDA', async () => {
      const creado = await crear(datosInsumo({ nivelMinimo: '2.5' }));
      const respuesta = await request(ap.servidor)
        .put(`${PREFIJO}/insumos/${creado.body.id}`)
        .set('Authorization', admin)
        .send(datosInsumo({ unidad: 'UNIDAD', nivelMinimo: '2.5', version: 0 }));
      expect([respuesta.status, respuesta.body.codigo]).toEqual([422, 'CANTIDAD_INVALIDA']);
    });
  });
});
