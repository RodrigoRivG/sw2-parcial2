import DataLoader from 'dataloader';

/** Un dato JSON tal como lo devolvió el servicio dueño. */
export type Dato = Record<string, unknown>;

/**
 * Una consulta por ID distinto dentro de la solicitud (RQ-GQL-05). Los servicios no tienen consultas por lote: la
 * función de lote hace una llamada por ID, en paralelo, y cada error queda solo en su elemento.
 */
export function cargador<T>(buscar: (id: string) => Promise<T | null>): DataLoader<string, T | null> {
  return new DataLoader<string, T | null>((ids) =>
    Promise.all(ids.map((id) => buscar(id).catch((error: unknown) => error as Error))),
  );
}
