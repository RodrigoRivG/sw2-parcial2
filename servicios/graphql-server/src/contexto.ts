import type { ClienteGateway, ContextoLlamada } from './fuentes/cliente-gateway';
import { FuenteGestion } from './fuentes/gestion.fuente';
import { FuenteIa } from './fuentes/ia.fuente';
import { FuenteInventario } from './fuentes/inventario.fuente';
import { FuenteOperaciones } from './fuentes/operaciones.fuente';
import type { Usuario } from './seguridad/validar-token';

/** Contexto de Apollo: vive una sola solicitud, con sus cargadores, su plazo y su presupuesto de llamadas. */
export interface Contexto extends ContextoLlamada {
  usuario: Usuario;
  gestion: FuenteGestion;
  inventario: FuenteInventario;
  operaciones: FuenteOperaciones;
  ia: FuenteIa;
}

export function crearContexto(cliente: ClienteGateway, locales: Record<string, unknown>): Contexto {
  const llamada: ContextoLlamada = {
    idCorrelacion: locales.idCorrelacion as string,
    senalPlazo: locales.senalPlazo as AbortSignal,
    estadisticas: locales.estadisticas as ContextoLlamada['estadisticas'],
  };
  return {
    ...llamada,
    usuario: locales.usuario as Usuario,
    gestion: new FuenteGestion(cliente, llamada),
    inventario: new FuenteInventario(cliente, llamada),
    operaciones: new FuenteOperaciones(cliente, llamada),
    ia: new FuenteIa(cliente, llamada),
  };
}
