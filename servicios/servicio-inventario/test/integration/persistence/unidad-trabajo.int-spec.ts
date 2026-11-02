import { contextoCorrelacion } from '../../../src/adapters/contexto-correlacion';
import { RegistroAuditoriaMongo } from '../../../src/adapters/outbound/persistence/registro-auditoria.mongo';
import { UnidadTrabajoMongo } from '../../../src/adapters/outbound/persistence/unidad-trabajo.mongo';
import { AplicacionPrueba, crearAplicacionPrueba } from '../soporte/aplicacion-prueba';

describe('Unidad de trabajo y auditoría en MongoDB', () => {
  let ap: AplicacionPrueba;
  let unidadTrabajo: UnidadTrabajoMongo;
  let auditoria: RegistroAuditoriaMongo;

  beforeAll(async () => {
    ap = await crearAplicacionPrueba();
    unidadTrabajo = ap.app.get(UnidadTrabajoMongo);
    auditoria = ap.app.get(RegistroAuditoriaMongo);
  });

  afterAll(() => ap.cerrar());

  beforeEach(() => ap.conexion.collection('registros_auditoria').deleteMany({}));

  const registro = { actor: 'admin-1', accion: 'CREAR', entidad: 'Insumo', idEntidad: 'i-1' } as const;

  it('guarda la auditoría con actor e idCorrelacion dentro de la transacción', async () => {
    const resultado = await contextoCorrelacion.run({ idCorrelacion: 'corr-uow' }, () =>
      unidadTrabajo.ejecutar(async () => {
        await auditoria.registrar(registro);
        return 'hecho';
      }),
    );
    expect(resultado).toBe('hecho');
    const guardados = await ap.conexion.collection('registros_auditoria').find({}).toArray();
    expect(guardados).toEqual([
      expect.objectContaining({
        actor: 'admin-1',
        accion: 'CREAR',
        entidad: 'Insumo',
        id_entidad: 'i-1',
        id_correlacion: 'corr-uow',
        fecha: expect.any(Date),
      }),
    ]);
  });

  it('si el trabajo falla, no se guarda nada (rollback)', async () => {
    await expect(
      unidadTrabajo.ejecutar(async () => {
        await auditoria.registrar(registro);
        throw new Error('falla después de escribir');
      }),
    ).rejects.toThrow('falla después de escribir');
    expect(await ap.conexion.collection('registros_auditoria').countDocuments()).toBe(0);
  });

  it('una unidad de trabajo anidada usa la misma transacción', async () => {
    await expect(
      unidadTrabajo.ejecutar(async () => {
        await unidadTrabajo.ejecutar(() => auditoria.registrar(registro));
        throw new Error('falla en la externa');
      }),
    ).rejects.toThrow('falla en la externa');
    expect(await ap.conexion.collection('registros_auditoria').countDocuments()).toBe(0);
  });

  it('las migraciones quedaron registradas y el índice único existe', async () => {
    const migraciones = await ap.conexion.collection('migraciones').find({}).toArray();
    expect(migraciones.map((m) => m._id)).toEqual([
      '001-crear-indices-auditoria',
      '002-crear-indices-insumos',
      '003-crear-indices-movimientos',
      '004-crear-coleccion-sagas',
    ]);
    const colecciones = await ap.conexion.db?.listCollections({ name: 'sagas_procesadas' }).toArray();
    expect(colecciones).toHaveLength(1);
    const indicesMovimientos = await ap.conexion.collection('movimientos_inventario').indexes();
    expect(indicesMovimientos.find((i) => i.key.id_saga === 1)?.partialFilterExpression).toEqual({
      id_saga: { $type: 'string' },
    });
    const indices = await ap.conexion.collection('insumos').indexes();
    expect(indices.find((i) => i.name === 'ux_insumos_nombre_normalizado')?.unique).toBe(true);
  });
});
