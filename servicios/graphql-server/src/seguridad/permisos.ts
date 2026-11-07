import { ErrorCampo } from '../web/errores';
import type { Usuario } from './validar-token';

/** Roles que pueden usar el servidor (constitución §5). */
export const ROLES_USUARIO = ['administrador', 'gerencia'];

const AMBOS = ['administrador', 'gerencia'] as const;
const GERENCIA = ['gerencia'] as const;

/**
 * Tabla de 1.3: cada campo que consulta un servicio se entrega solo a los roles que el servicio dueño autoriza
 * para esos datos. La clave es `Tipo.campo` del esquema; `aplicarPermisos` la usa para envolver los resolvers.
 */
export const PERMISOS: Record<string, readonly string[]> = {
  'Query.parcelas': AMBOS,
  'Query.cultivos': AMBOS,
  'Query.campanias': AMBOS,
  'Query.campania': AMBOS,
  'Query.campaniasFinalizadas': AMBOS,
  'Query.estadoInventario': AMBOS,
  'Query.insumos': AMBOS,
  'Query.labores': AMBOS,
  'Query.incidencias': AMBOS,
  'Query.analisis': GERENCIA,
  'Query.analisisPorId': GERENCIA,
  'Campania.parcela': AMBOS,
  'Campania.cultivo': AMBOS,
  'Campania.indicadores': AMBOS,
  'Campania.costos': AMBOS,
  'Campania.produccion': AMBOS,
  'Campania.predicciones': GERENCIA,
  'Campania.labores': AMBOS,
  'Campania.incidencias': AMBOS,
  'Labor.parcela': AMBOS,
  'Labor.campania': AMBOS,
  'Incidencia.parcela': AMBOS,
  'Incidencia.campania': AMBOS,
  'Anomalia.campania': AMBOS,
  'ConsumoInsumo.insumo': AMBOS,
};

export function exigirRol(usuario: Usuario, roles: readonly string[]): void {
  if (!usuario.roles.some((rol) => roles.includes(rol))) {
    throw new ErrorCampo('SIN_PERMISO');
  }
}

type Resolver = (padre: unknown, argumentos: unknown, contexto: { usuario: Usuario }, info: unknown) => unknown;
type MapaResolvers = Record<string, Record<string, unknown>>;

/** Envuelve cada resolver de la tabla con su verificación de rol, antes de llamar a cualquier servicio. */
export function aplicarPermisos<T extends MapaResolvers>(resolvers: T): T {
  for (const [clave, roles] of Object.entries(PERMISOS)) {
    const [tipo, campo] = clave.split('.');
    const original = resolvers[tipo]?.[campo] as Resolver | undefined;
    if (!original) {
      throw new Error(`Falta el resolver ${clave} de la tabla de permisos`);
    }
    resolvers[tipo][campo] = ((padre, argumentos, contexto, info) => {
      exigirRol(contexto.usuario, roles);
      return original(padre, argumentos, contexto, info);
    }) satisfies Resolver;
  }
  return resolvers;
}
