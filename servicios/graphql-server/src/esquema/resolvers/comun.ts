import { TAMANIO_MAXIMO_PAGINA } from '../../config';
import type { Dato } from '../../fuentes/cargador';
import { ErrorCampo } from '../../web/errores';

export type Argumentos = Record<string, unknown>;

const CATEGORIAS_COSTO = ['INSUMO', 'MANO_DE_OBRA', 'MAQUINARIA', 'OTRO'];

/** `{ "INSUMO": "820.50", … }` → lista en el orden de `CategoriaCosto`, sin cambiar ningún monto (2.3). */
export function aMontos(montos: unknown): { categoria: string; monto: unknown }[] {
  const objeto = (montos ?? {}) as Dato;
  return CATEGORIAS_COSTO.filter((categoria) => categoria in objeto).map((categoria) => ({
    categoria,
    monto: objeto[categoria],
  }));
}

/** `pagina` desde 0 y `tamanio` o `limite` entre 1 y 50, antes de llamar al servicio (casos borde). */
export function validarPagina(argumentos: Argumentos): void {
  const pagina = argumentos.pagina as number | undefined;
  for (const nombre of ['tamanio', 'limite']) {
    const valor = argumentos[nombre] as number | undefined;
    if (valor !== undefined && (valor < 1 || valor > TAMANIO_MAXIMO_PAGINA)) {
      throw new ErrorCampo('DATOS_INVALIDOS', [`${nombre} debe estar entre 1 y ${TAMANIO_MAXIMO_PAGINA}`]);
    }
  }
  if (pagina !== undefined && pagina < 0) {
    throw new ErrorCampo('DATOS_INVALIDOS', ['pagina no puede ser negativa']);
  }
}

/** Argumentos de la consulta (y su filtro) como parámetros de la URL del servicio. */
export function parametros(argumentos: Argumentos, filtro = 'filtro'): Record<string, string | number | boolean> {
  validarPagina(argumentos);
  const { [filtro]: valoresFiltro, ...resto } = argumentos;
  return { ...(valoresFiltro as Argumentos | undefined), ...resto } as Record<string, string | number | boolean>;
}
