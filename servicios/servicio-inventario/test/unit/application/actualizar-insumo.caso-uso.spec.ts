import { ActualizarInsumoCasoUso } from '../../../src/application/use-cases/actualizar-insumo.caso-uso';
import { ErrorDominio } from '../../../src/domain/shared/error-dominio';
import { CategoriaInsumo } from '../../../src/domain/supply/categoria-insumo.enum';
import { Insumo } from '../../../src/domain/supply/insumo.entidad';
import { UnidadMedida } from '../../../src/domain/supply/unidad-medida.enum';
import {
  AuditoriaEnMemoria,
  RelojFijo,
  RepositorioInsumoEnMemoria,
  UnidadTrabajoDirecta,
} from './dobles';

const DATOS = {
  nombre: 'Urea 46 %',
  categoria: CategoriaInsumo.FERTILIZANTE,
  unidad: UnidadMedida.KILOGRAMO,
  nivelMinimo: '50',
  costoUnitario: '4.85',
};

describe('ActualizarInsumoCasoUso', () => {
  let repositorio: RepositorioInsumoEnMemoria;
  let auditoria: AuditoriaEnMemoria;
  let reloj: RelojFijo;
  let casoUso: ActualizarInsumoCasoUso;

  beforeEach(async () => {
    repositorio = new RepositorioInsumoEnMemoria();
    auditoria = new AuditoriaEnMemoria();
    reloj = new RelojFijo();
    casoUso = new ActualizarInsumoCasoUso(
      repositorio,
      new UnidadTrabajoDirecta(),
      auditoria,
      reloj,
    );
    await repositorio.guardarNuevo(Insumo.crear('i-1', DATOS, reloj.ahora()));
  });

  it('actualiza, incrementa la versión y audita MODIFICAR', async () => {
    reloj.instante = new Date('2026-11-03T08:00:00Z');
    const actualizado = await casoUso.ejecutar(
      'i-1',
      { ...DATOS, costoUnitario: '5.10', version: 0 },
      'admin-1',
    );
    expect(actualizado.costoUnitario.aTextoCostoUnitario()).toBe('5.1000');
    expect(actualizado.version).toBe(1);
    expect(actualizado.fechaActualizacion).toEqual(reloj.instante);
    expect(auditoria.registros).toEqual([
      { actor: 'admin-1', accion: 'MODIFICAR', entidad: 'Insumo', idEntidad: 'i-1' },
    ]);
  });

  it('responde INSUMO_NO_ENCONTRADO si el insumo no existe', async () => {
    await expect(
      casoUso.ejecutar('no-existe', { ...DATOS, version: 0 }, 'admin-1'),
    ).rejects.toMatchObject({ codigo: 'INSUMO_NO_ENCONTRADO', tipo: 'NO_ENCONTRADO' });
  });

  it('responde CONFLICTO_CONCURRENCIA si la versión enviada no es la actual', async () => {
    await expect(
      casoUso.ejecutar('i-1', { ...DATOS, version: 7 }, 'admin-1'),
    ).rejects.toMatchObject({ codigo: 'CONFLICTO_CONCURRENCIA', tipo: 'CONFLICTO' });
    expect(auditoria.registros).toHaveLength(0);
  });

  it('responde CONFLICTO_CONCURRENCIA si otra transacción guardó antes', async () => {
    repositorio.forzarConflicto = true;
    await expect(
      casoUso.ejecutar('i-1', { ...DATOS, version: 0 }, 'admin-1'),
    ).rejects.toBeInstanceOf(ErrorDominio);
    expect(auditoria.registros).toHaveLength(0);
  });

  it('propaga las reglas del dominio sin auditar', async () => {
    await expect(
      casoUso.ejecutar('i-1', { ...DATOS, nivelMinimo: '-1', version: 0 }, 'admin-1'),
    ).rejects.toMatchObject({ codigo: 'NIVEL_MINIMO_INVALIDO' });
    expect(auditoria.registros).toHaveLength(0);
  });
});
