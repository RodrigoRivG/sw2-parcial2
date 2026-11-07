import type { Contexto } from '../../contexto';
import type { Dato } from '../../fuentes/cargador';
import { aplicarPermisos } from '../../seguridad/permisos';
import { Decimal, Fecha, FechaHora } from '../escalares';
import { aMontos, parametros, validarPagina, type Argumentos } from './comun';

type C = Contexto;

/**
 * Cada resolver solo llama a su fuente y copia los valores tal como llegan (constitución §3). La verificación de
 * rol de cada campo la agrega `aplicarPermisos` con la tabla de 1.3.
 */
export function crearResolvers() {
  const resolvers = {
    Decimal,
    Fecha,
    FechaHora,

    Query: {
      parcelas: (_: unknown, a: Argumentos, c: C) => c.gestion.listar('parcelas', parametros(a)),
      cultivos: (_: unknown, a: Argumentos, c: C) => c.gestion.listar('cultivos', parametros(a)),
      campanias: (_: unknown, a: Argumentos, c: C) => c.gestion.listar('campanias', parametros(a)),
      campania: (_: unknown, a: { id: string }, c: C) => c.gestion.campania.load(a.id),
      campaniasFinalizadas: (_: unknown, a: Argumentos, c: C) =>
        c.gestion.listar('campanias/historicos', parametros(a)),
      estadoInventario: (_: unknown, a: Argumentos, c: C) => c.inventario.listar('estado-inventario', parametros(a)),
      insumos: (_: unknown, a: Argumentos, c: C) => c.inventario.listar('insumos', parametros(a)),
      labores: (_: unknown, a: Argumentos, c: C) => c.operaciones.listar('labores', parametros(a)),
      incidencias: (_: unknown, a: Argumentos, c: C) => c.operaciones.listar('incidencias', parametros(a)),
      analisis: (_: unknown, a: Argumentos, c: C) => c.ia.listar('analisis', parametros(a)),
      analisisPorId: (_: unknown, a: { id: string }, c: C) => c.ia.analisis(a.id),
    },

    Campania: {
      parcela: (p: Dato, _: unknown, c: C) => c.gestion.parcela.load(p.idParcela as string),
      cultivo: (p: Dato, _: unknown, c: C) => c.gestion.cultivo.load(p.idCultivo as string),
      indicadores: (p: Dato, _: unknown, c: C) => c.gestion.indicadores.load(p.id as string),
      costos: async (p: Dato, _: unknown, c: C) => {
        const costos = await c.gestion.costos.load(p.id as string);
        return costos && { costoTotal: costos.costoTotal, subtotalesPorCategoria: aMontos(costos.subtotalesPorCategoria) };
      },
      produccion: (p: Dato, _: unknown, c: C) => c.gestion.produccion.load(p.id as string),
      predicciones: (p: Dato, a: Argumentos, c: C) => c.ia.listar('predicciones', { ...parametros(a), idCampania: p.id as string }),
      labores: (p: Dato, a: Argumentos, c: C) => {
        validarPagina(a);
        return c.operaciones.listar('labores', { ...a, idCampania: p.id as string } as Record<string, string>);
      },
      incidencias: (p: Dato, a: Argumentos, c: C) => {
        validarPagina(a);
        return c.operaciones.listar('incidencias', { ...a, idCampania: p.id as string } as Record<string, string>);
      },
    },

    CampaniaFinalizada: {
      costosPorCategoria: (p: Dato) => aMontos(p.costosPorCategoria),
    },

    Labor: {
      parcela: (p: Dato, _: unknown, c: C) => c.gestion.parcela.load(p.idParcela as string),
      campania: (p: Dato, _: unknown, c: C) => c.gestion.campania.load(p.idCampania as string),
    },

    ConsumoInsumo: {
      insumo: (p: Dato, _: unknown, c: C) => c.inventario.insumo.load(p.idInsumo as string),
    },

    Incidencia: {
      parcela: (p: Dato, _: unknown, c: C) => c.gestion.parcela.load(p.idParcela as string),
      campania: (p: Dato, _: unknown, c: C) => (p.idCampania ? c.gestion.campania.load(p.idCampania as string) : null),
    },

    Prediccion: {
      costosPorHectarea: (p: Dato) => aMontos(p.costosPorHectarea),
    },

    Anomalia: {
      campania: (p: Dato, _: unknown, c: C) => c.gestion.campania.load(p.idCampania as string),
    },
  };
  return aplicarPermisos(resolvers as unknown as Record<string, Record<string, unknown>>);
}
