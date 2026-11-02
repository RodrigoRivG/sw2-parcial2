import { EvaluarStockBajoCasoUso } from '../../../src/application/use-cases/evaluar-stock-bajo.caso-uso';
import { Cantidad } from '../../../src/domain/shared/cantidad.vo';
import { CategoriaInsumo } from '../../../src/domain/supply/categoria-insumo.enum';
import { Insumo } from '../../../src/domain/supply/insumo.entidad';
import { DURACION_RESERVA_ALERTA_MS } from '../../../src/domain/supply/politica-stock-bajo';
import { UnidadMedida } from '../../../src/domain/supply/unidad-medida.enum';
import { PublicadorEnMemoria, RelojFijo, RepositorioInsumoEnMemoria, copiarInsumo } from './dobles';

describe('EvaluarStockBajoCasoUso', () => {
  let insumos: RepositorioInsumoEnMemoria;
  let publicador: PublicadorEnMemoria;
  let reloj: RelojFijo;
  let casoUso: EvaluarStockBajoCasoUso;

  beforeEach(async () => {
    insumos = new RepositorioInsumoEnMemoria();
    publicador = new PublicadorEnMemoria();
    reloj = new RelojFijo();
    casoUso = new EvaluarStockBajoCasoUso(insumos, publicador, reloj);
    const urea = Insumo.crear(
      'urea',
      {
        nombre: 'Urea',
        categoria: CategoriaInsumo.FERTILIZANTE,
        unidad: UnidadMedida.KILOGRAMO,
        nivelMinimo: '50',
        costoUnitario: '4.85',
      },
      reloj.ahora(),
    );
    await insumos.guardarNuevo(
      copiarInsumo(urea, { stock: Cantidad.de('50', UnidadMedida.KILOGRAMO) }),
    );
  });

  it('publica el evento con los datos del insumo y guarda la fecha de la alerta', async () => {
    expect(await casoUso.ejecutar(['urea', 'urea'], 'corr-1')).toEqual([
      { idInsumo: 'urea', resultado: 'PUBLICADA' },
    ]);
    expect(publicador.publicados).toEqual([
      {
        routingKey: 'inventario.stock.bajo',
        tipo: 'StockBajo',
        idCorrelacion: 'corr-1',
        datos: {
          idInsumo: 'urea',
          nombre: 'Urea',
          stock: '50.000',
          nivelMinimo: '50.000',
          unidad: 'KILOGRAMO',
        },
      },
    ]);
    const guardado = await insumos.buscarPorId('urea');
    expect(guardado?.fechaUltimaAlerta).toEqual(reloj.ahora());
    expect(guardado?.reservaAlertaHasta).toBeNull();
  });

  it('dentro de las 24 h no vuelve a publicar', async () => {
    await casoUso.ejecutar(['urea']);
    reloj.instante = new Date(reloj.instante.getTime() + 60 * 60 * 1000);
    expect(await casoUso.ejecutar(['urea'])).toEqual([
      { idInsumo: 'urea', resultado: 'NO_CORRESPONDE' },
    ]);
    expect(publicador.publicados).toHaveLength(1);
  });

  it('si otro proceso tiene la reserva, no publica', async () => {
    const actual = await insumos.buscarPorId('urea');
    await insumos.guardarNuevo(
      copiarInsumo(actual as Insumo, {
        reservaAlertaHasta: new Date(reloj.instante.getTime() + DURACION_RESERVA_ALERTA_MS),
      }),
    );
    expect((await casoUso.ejecutar(['urea']))[0].resultado).toBe('NO_CORRESPONDE');
    // Reserva perdida entre la lectura y la escritura.
    const sinReserva = copiarInsumo(actual as Insumo, { reservaAlertaHasta: null });
    await insumos.guardarNuevo(sinReserva);
    jest.spyOn(insumos, 'reservarAlerta').mockResolvedValueOnce(false);
    expect((await casoUso.ejecutar(['urea']))[0].resultado).toBe('RESERVADA_POR_OTRO');
    expect(publicador.publicados).toHaveLength(0);
  });

  it('si la publicación falla, libera la reserva sin guardar la fecha, y el siguiente intento publica', async () => {
    publicador.fallar = true;
    const [fallo] = await casoUso.ejecutar(['urea']);
    expect(fallo.resultado).toBe('FALLIDA');
    expect((fallo.error as Error).message).toBe('Broker no disponible');
    const tras = await insumos.buscarPorId('urea');
    expect(tras?.fechaUltimaAlerta).toBeNull();
    expect(tras?.reservaAlertaHasta).toBeNull();

    publicador.fallar = false;
    expect((await casoUso.ejecutar(['urea']))[0].resultado).toBe('PUBLICADA');
  });

  it('un insumo inexistente no corresponde; un error del repositorio queda como FALLIDA', async () => {
    expect((await casoUso.ejecutar(['otro']))[0].resultado).toBe('NO_CORRESPONDE');
    jest.spyOn(insumos, 'buscarPorId').mockRejectedValueOnce(new Error('MongoDB caído'));
    expect((await casoUso.ejecutar(['urea']))[0].resultado).toBe('FALLIDA');
  });
});
