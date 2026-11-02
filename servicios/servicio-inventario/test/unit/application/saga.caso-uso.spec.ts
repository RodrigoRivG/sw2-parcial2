import { DescontarInsumosCasoUso } from '../../../src/application/use-cases/descontar-insumos.caso-uso';
import { RegistrarMovimientoCasoUso } from '../../../src/application/use-cases/registrar-movimiento.caso-uso';
import { ComandoNoProcesable } from '../../../src/application/use-cases/respuestas-saga';
import { RestaurarInsumosCasoUso } from '../../../src/application/use-cases/restaurar-insumos.caso-uso';
import { TipoMovimiento } from '../../../src/domain/movement/tipo-movimiento.enum';
import { Cantidad } from '../../../src/domain/shared/cantidad.vo';
import { CategoriaInsumo } from '../../../src/domain/supply/categoria-insumo.enum';
import { Insumo } from '../../../src/domain/supply/insumo.entidad';
import { UnidadMedida } from '../../../src/domain/supply/unidad-medida.enum';
import {
  AuditoriaEnMemoria,
  RelojFijo,
  RepositorioInsumoEnMemoria,
  RepositorioMovimientoEnMemoria,
  SagasEnMemoria,
  UnidadTrabajoDirecta,
} from './dobles';

const SAGA = '5d7c2a1e-0b3f-4c55-9a1e-3f2b1c0d9e8a';
const LABOR = '7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d';
const UREA = '0b6f1c6e-2f7a-4a7e-9a39-7d5a1c2b3d4e';
const GLIFOSATO = '1c7f2d7f-3a8b-4b8f-8b4a-8e6b2d3c4e5f';
const TRAMPA = '2d8a3e8a-4b9c-4c9a-9c5b-9f7c3e4d5f6a';
const INEXISTENTE = '3e9b4f9b-5cad-4dab-ad6c-a08d4f5e6a7b';
const SOBRE = { version: 1, idCorrelacion: SAGA, origen: 'servicio-operaciones' };

describe('DescontarInsumosCasoUso y RestaurarInsumosCasoUso', () => {
  let insumos: RepositorioInsumoEnMemoria;
  let movimientos: RepositorioMovimientoEnMemoria;
  let auditoria: AuditoriaEnMemoria;
  let sagas: SagasEnMemoria;
  let descontar: DescontarInsumosCasoUso;
  let restaurar: RestaurarInsumosCasoUso;

  async function cargar(id: string, nombre: string, unidad: UnidadMedida, costo: string, stock: string) {
    const reloj = new RelojFijo();
    await insumos.guardarNuevo(
      Insumo.crear(
        id,
        { nombre, categoria: CategoriaInsumo.FERTILIZANTE, unidad, nivelMinimo: '0', costoUnitario: costo },
        reloj.ahora(),
      ),
    );
    await insumos.aplicarMovimiento(id, TipoMovimiento.ENTRADA, Cantidad.de(stock, unidad), reloj.ahora());
  }

  beforeEach(async () => {
    insumos = new RepositorioInsumoEnMemoria();
    movimientos = new RepositorioMovimientoEnMemoria();
    auditoria = new AuditoriaEnMemoria();
    sagas = new SagasEnMemoria();
    const reloj = new RelojFijo();
    const unidadTrabajo = new UnidadTrabajoDirecta();
    const registrar = new RegistrarMovimientoCasoUso(insumos, movimientos, unidadTrabajo, auditoria, reloj);
    descontar = new DescontarInsumosCasoUso(insumos, sagas, registrar, unidadTrabajo, reloj);
    restaurar = new RestaurarInsumosCasoUso(movimientos, sagas, registrar, unidadTrabajo, reloj);
    await cargar(UREA, 'Urea', UnidadMedida.KILOGRAMO, '4.85', '200');
    await cargar(GLIFOSATO, 'Glifosato', UnidadMedida.LITRO, '38.20', '50');
    await cargar(TRAMPA, 'Trampa', UnidadMedida.UNIDAD, '0.1235', '10');
  });

  const comando = (items: { idInsumo: string; cantidad: string }[]) => ({
    idSaga: SAGA,
    idLabor: LABOR,
    items,
  });

  it('descuenta todo, calcula el costo total y audita con el origen como actor', async () => {
    const resultado = await descontar.ejecutar(
      comando([
        { idInsumo: UREA, cantidad: '100' },
        { idInsumo: GLIFOSATO, cantidad: '2.5' },
      ]),
      SOBRE,
    );
    expect(resultado.respuesta).toEqual({
      tipo: 'InsumosDescontados',
      datos: {
        idSaga: SAGA,
        idLabor: LABOR,
        costoTotal: '580.50',
        items: [
          { idInsumo: UREA, cantidad: '100.000', costoUnitario: '4.8500' },
          { idInsumo: GLIFOSATO, cantidad: '2.500', costoUnitario: '38.2000' },
        ],
      },
    });
    expect(resultado.insumosAfectados).toEqual([UREA, GLIFOSATO]);
    expect((await insumos.buscarPorId(UREA))?.stock.aTexto()).toBe('100.000');
    expect(movimientos.movimientos.map((m) => [m.motivo, m.actor, m.idSaga])).toEqual([
      [`Labor ${LABOR}`, 'servicio-operaciones', SAGA],
      [`Labor ${LABOR}`, 'servicio-operaciones', SAGA],
    ]);
    expect(auditoria.registros.map((r) => r.accion)).toEqual([
      'DESCONTAR_INSUMOS_SAGA',
      'DESCONTAR_INSUMOS_SAGA',
    ]);
  });

  it('redondea solo al final: 3 × 0,1235 = 0,3705 → "0.37"', async () => {
    const resultado = await descontar.ejecutar(comando([{ idInsumo: TRAMPA, cantidad: '3' }]), SOBRE);
    expect(resultado.respuesta.datos.costoTotal).toBe('0.37');
  });

  it('prioridad de rechazos: inexistente, luego decimales con UNIDAD, luego stock', async () => {
    const todos = [
      { idInsumo: INEXISTENTE, cantidad: '1' },
      { idInsumo: TRAMPA, cantidad: '1.5' },
      { idInsumo: UREA, cantidad: '999' },
    ];
    const codigo = async (items: typeof todos, saga: string) =>
      (
        await descontar.ejecutar({ ...comando(items), idSaga: saga }, { ...SOBRE, idCorrelacion: saga })
      ).respuesta.datos;
    expect(await codigo(todos, SAGA)).toMatchObject({
      codigo: 'INSUMO_NO_ENCONTRADO',
      insumosAfectados: [{ idInsumo: INEXISTENTE, cantidadSolicitada: '1.000', stockDisponible: null }],
    });
    const otraSaga = '6e8d3b2f-1c4a-4d66-8b2f-4a3c2d1e0f9b';
    expect(await codigo(todos.slice(1), otraSaga)).toMatchObject({
      codigo: 'DATOS_INVALIDOS',
      insumosAfectados: [{ idInsumo: TRAMPA, cantidadSolicitada: '1.500', stockDisponible: '10.000' }],
    });
    const terceraSaga = '7f9e4c3a-2d5b-4e77-9c3a-5b4d3e2f1a0c';
    expect(await codigo(todos.slice(2), terceraSaga)).toMatchObject({
      codigo: 'STOCK_INSUFICIENTE',
      insumosAfectados: [{ idInsumo: UREA, cantidadSolicitada: '999.000', stockDisponible: '200.000' }],
    });
    expect(movimientos.movimientos).toHaveLength(0);
  });

  it('un formato inválido se responde sin guardar resultado', async () => {
    const resultado = await descontar.ejecutar(comando([]), SOBRE);
    expect(resultado.respuesta.datos).toMatchObject({ codigo: 'DATOS_INVALIDOS', idSaga: SAGA });
    expect(sagas.sagas.size).toBe(0);
  });

  it('un comando repetido con otros items repite el original y lo advierte', async () => {
    await descontar.ejecutar(comando([{ idInsumo: UREA, cantidad: '10' }]), SOBRE);
    const igual = await descontar.ejecutar(comando([{ idInsumo: UREA, cantidad: '10.000' }]), SOBRE);
    expect(igual.advertencia).toBeUndefined();
    const distinto = await descontar.ejecutar(comando([{ idInsumo: UREA, cantidad: '20' }]), SOBRE);
    expect(distinto.advertencia).toContain('otros items');
    expect(distinto.respuesta.datos.costoTotal).toBe('48.50');
    expect(distinto.insumosAfectados).toEqual([]);
  });

  it('restaura con el costo de la salida y repite la respuesta; el descuento tardío se rechaza', async () => {
    await descontar.ejecutar(comando([{ idInsumo: UREA, cantidad: '10' }]), SOBRE);
    const restauracion = await restaurar.ejecutar({ idSaga: SAGA, idLabor: LABOR }, SOBRE);
    expect(restauracion.respuesta).toEqual({
      tipo: 'InsumosRestaurados',
      datos: {
        idSaga: SAGA,
        idLabor: LABOR,
        sinEfecto: false,
        items: [{ idInsumo: UREA, cantidad: '10.000' }],
      },
    });
    expect((await insumos.buscarPorId(UREA))?.stock.aTexto()).toBe('200.000');
    const entrada = movimientos.movimientos.find((m) => m.tipo === TipoMovimiento.ENTRADA);
    expect(entrada?.motivo).toBe(`Compensación de saga ${SAGA}`);
    expect(entrada?.costoUnitario.aTextoCostoUnitario()).toBe('4.8500');
    expect(auditoria.registros.at(-1)?.accion).toBe('RESTAURAR_INSUMOS_SAGA');
    expect((await restaurar.ejecutar({ idSaga: SAGA, idLabor: LABOR }, SOBRE)).respuesta).toEqual(
      restauracion.respuesta,
    );

    const otra = '6e8d3b2f-1c4a-4d66-8b2f-4a3c2d1e0f9b';
    const sobreOtra = { ...SOBRE, idCorrelacion: otra };
    const sinDescuento = await restaurar.ejecutar({ idSaga: otra, idLabor: LABOR }, sobreOtra);
    expect(sinDescuento.respuesta.datos).toMatchObject({ sinEfecto: true, items: [] });
    const tardio = await descontar.ejecutar(
      { ...comando([{ idInsumo: UREA, cantidad: '1' }]), idSaga: otra },
      sobreOtra,
    );
    expect(tardio.respuesta.datos).toMatchObject({ codigo: 'SAGA_COMPENSADA' });
  });

  it('una restauración con idLabor distinto restaura igual y lo advierte', async () => {
    await descontar.ejecutar(comando([{ idInsumo: UREA, cantidad: '10' }]), SOBRE);
    const otraLabor = '8a0f5d4b-3e6c-4f88-ad4b-6c5e4f3a2b1d';
    const resultado = await restaurar.ejecutar({ idSaga: SAGA, idLabor: otraLabor }, SOBRE);
    expect(resultado.advertencia).toContain('idLabor');
    expect(resultado.respuesta.datos).toMatchObject({ sinEfecto: false });
  });

  it.each([
    ['idSaga inválido', { idSaga: 'S1', idLabor: LABOR }, SOBRE],
    ['versión 2', { idSaga: SAGA, idLabor: LABOR }, { ...SOBRE, version: 2 }],
    ['idCorrelacion distinto', { idSaga: SAGA, idLabor: LABOR }, { ...SOBRE, idCorrelacion: LABOR }],
  ])('RestaurarInsumos con %s → ComandoNoProcesable (DLQ)', async (_caso, datos, sobre) => {
    await expect(restaurar.ejecutar(datos, sobre)).rejects.toBeInstanceOf(ComandoNoProcesable);
  });
});
