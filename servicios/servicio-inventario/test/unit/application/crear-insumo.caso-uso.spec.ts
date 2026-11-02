import { ConsultarInsumosCasoUso } from '../../../src/application/use-cases/consultar-insumos.caso-uso';
import { CrearInsumoCasoUso } from '../../../src/application/use-cases/crear-insumo.caso-uso';
import { CategoriaInsumo } from '../../../src/domain/supply/categoria-insumo.enum';
import { UnidadMedida } from '../../../src/domain/supply/unidad-medida.enum';
import {
  AuditoriaEnMemoria,
  RelojFijo,
  RepositorioInsumoEnMemoria,
  UnidadTrabajoDirecta,
} from './dobles';

const DATOS = {
  nombre: 'Glifosato',
  categoria: CategoriaInsumo.FITOSANITARIO,
  unidad: UnidadMedida.LITRO,
  nivelMinimo: '20',
  costoUnitario: '38.20',
};

describe('CrearInsumoCasoUso y ConsultarInsumosCasoUso', () => {
  let repositorio: RepositorioInsumoEnMemoria;
  let auditoria: AuditoriaEnMemoria;
  let crear: CrearInsumoCasoUso;
  let consultar: ConsultarInsumosCasoUso;

  beforeEach(() => {
    repositorio = new RepositorioInsumoEnMemoria();
    auditoria = new AuditoriaEnMemoria();
    crear = new CrearInsumoCasoUso(
      repositorio,
      new UnidadTrabajoDirecta(),
      auditoria,
      new RelojFijo(),
    );
    consultar = new ConsultarInsumosCasoUso(repositorio);
  });

  it('crea el insumo con un UUID, lo guarda y audita CREAR', async () => {
    const insumo = await crear.ejecutar({ ...DATOS, stockInicial: '0' }, 'admin-1');
    expect(insumo.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(await consultar.obtener(insumo.id)).toBe(insumo);
    expect(auditoria.registros).toEqual([
      { actor: 'admin-1', accion: 'CREAR', entidad: 'Insumo', idEntidad: insumo.id },
    ]);
  });

  it('valida el stock inicial con la unidad del insumo antes de guardar', async () => {
    await expect(
      crear.ejecutar(
        { ...DATOS, unidad: UnidadMedida.UNIDAD, stockInicial: '10.5' },
        'admin-1',
      ),
    ).rejects.toMatchObject({ codigo: 'CANTIDAD_INVALIDA' });
    await expect(crear.ejecutar({ ...DATOS, stockInicial: '-5' }, 'admin-1')).rejects.toMatchObject(
      { codigo: 'CANTIDAD_INVALIDA' },
    );
    expect(repositorio.insumos.size).toBe(0);
  });

  it('obtener responde INSUMO_NO_ENCONTRADO y listar delega en el repositorio', async () => {
    await expect(consultar.obtener('no-existe')).rejects.toMatchObject({
      codigo: 'INSUMO_NO_ENCONTRADO',
    });
    await crear.ejecutar(DATOS, 'admin-1');
    const pagina = await consultar.listar({}, { pagina: 0, tamanio: 20 });
    expect(pagina.total).toBe(1);
  });
});
