import { ConsultarMovimientosCasoUso } from '../../../src/application/use-cases/consultar-movimientos.caso-uso';
import { RegistrarMovimientoCasoUso } from '../../../src/application/use-cases/registrar-movimiento.caso-uso';
import { TipoMovimiento } from '../../../src/domain/movement/tipo-movimiento.enum';
import { CategoriaInsumo } from '../../../src/domain/supply/categoria-insumo.enum';
import { Insumo } from '../../../src/domain/supply/insumo.entidad';
import { UnidadMedida } from '../../../src/domain/supply/unidad-medida.enum';
import {
  AuditoriaEnMemoria,
  RelojFijo,
  RepositorioInsumoEnMemoria,
  RepositorioMovimientoEnMemoria,
  UnidadTrabajoDirecta,
} from './dobles';

describe('RegistrarMovimientoCasoUso y ConsultarMovimientosCasoUso', () => {
  let insumos: RepositorioInsumoEnMemoria;
  let movimientos: RepositorioMovimientoEnMemoria;
  let auditoria: AuditoriaEnMemoria;
  let casoUso: RegistrarMovimientoCasoUso;
  let consultar: ConsultarMovimientosCasoUso;

  beforeEach(async () => {
    insumos = new RepositorioInsumoEnMemoria();
    movimientos = new RepositorioMovimientoEnMemoria();
    auditoria = new AuditoriaEnMemoria();
    const reloj = new RelojFijo();
    casoUso = new RegistrarMovimientoCasoUso(
      insumos,
      movimientos,
      new UnidadTrabajoDirecta(),
      auditoria,
      reloj,
    );
    consultar = new ConsultarMovimientosCasoUso(movimientos);
    await insumos.guardarNuevo(
      Insumo.crear(
        'urea',
        {
          nombre: 'Urea',
          categoria: CategoriaInsumo.FERTILIZANTE,
          unidad: UnidadMedida.KILOGRAMO,
          nivelMinimo: '50',
          costoUnitario: '4.85',
        },
        reloj.ahora(),
      ),
    );
  });

  const entrada = (tipo: TipoMovimiento, cantidad: string) => ({
    idInsumo: 'urea',
    tipo,
    cantidad,
    motivo: 'Prueba',
  });

  it('aplica el movimiento, guarda el stock resultante y audita REGISTRAR_MOVIMIENTO', async () => {
    const movimiento = await casoUso.ejecutar(entrada(TipoMovimiento.ENTRADA, '120'), 'admin-1');
    expect(movimiento.stockResultante.aTexto()).toBe('120.000');
    expect((await insumos.buscarPorId('urea'))?.stock.aTexto()).toBe('120.000');
    expect(await consultar.obtener(movimiento.id)).toBe(movimiento);
    expect(auditoria.registros).toEqual([
      {
        actor: 'admin-1',
        accion: 'REGISTRAR_MOVIMIENTO',
        entidad: 'MovimientoInventario',
        idEntidad: movimiento.id,
      },
    ]);
  });

  it('responde INSUMO_NO_ENCONTRADO si el insumo no existe', async () => {
    await expect(
      casoUso.ejecutar({ ...entrada(TipoMovimiento.ENTRADA, '1'), idInsumo: 'otro' }, 'admin-1'),
    ).rejects.toMatchObject({ codigo: 'INSUMO_NO_ENCONTRADO' });
  });

  it('una salida mayor al stock leído → STOCK_INSUFICIENTE, sin guardar ni auditar', async () => {
    await expect(
      casoUso.ejecutar(entrada(TipoMovimiento.SALIDA, '1'), 'admin-1'),
    ).rejects.toMatchObject({ codigo: 'STOCK_INSUFICIENTE' });
    expect(movimientos.movimientos).toHaveLength(0);
    expect(auditoria.registros).toHaveLength(0);
  });

  it('carrera perdida en la escritura → STOCK_INSUFICIENTE, sin guardar ni auditar', async () => {
    await casoUso.ejecutar(entrada(TipoMovimiento.ENTRADA, '10'), 'admin-1');
    insumos.forzarCarreraPerdida = true;
    await expect(
      casoUso.ejecutar(entrada(TipoMovimiento.SALIDA, '5'), 'admin-1'),
    ).rejects.toMatchObject({ codigo: 'STOCK_INSUFICIENTE' });
    expect(movimientos.movimientos).toHaveLength(1);
    expect(auditoria.registros).toHaveLength(1);
  });

  it('obtener responde MOVIMIENTO_NO_ENCONTRADO; listar delega en el repositorio', async () => {
    await expect(consultar.obtener('no-existe')).rejects.toMatchObject({
      codigo: 'MOVIMIENTO_NO_ENCONTRADO',
    });
    await casoUso.ejecutar(entrada(TipoMovimiento.ENTRADA, '10'), 'admin-1');
    expect((await consultar.listar({}, { pagina: 0, tamanio: 20 })).total).toBe(1);
  });
});
