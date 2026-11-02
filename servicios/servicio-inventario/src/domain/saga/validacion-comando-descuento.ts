import { InsumoAfectado } from './saga-procesada.entidad';

const PATRON_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** Texto decimal positivo con hasta 3 decimales; un número JSON no es válido (convención común). */
const PATRON_CANTIDAD = /^\d{1,12}(\.\d{1,3})?$/;

export interface ItemComandoDescuento {
  idInsumo: string;
  cantidad: string;
}

export interface ComandoDescuento {
  idSaga: string;
  idLabor: string;
  items: ItemComandoDescuento[];
}

export type ValidacionDescuento =
  | { valido: true; comando: ComandoDescuento }
  | {
      valido: false;
      motivo: string;
      /** Lo que se pueda leer del comando, para responder aunque sea inválido. */
      idSaga: string | null;
      idLabor: string | null;
      insumosAfectados: InsumoAfectado[];
    };

export function esUuid(valor: unknown): valor is string {
  return typeof valor === 'string' && PATRON_UUID.test(valor);
}

/** RQ-SAG-02, paso 2: formato de `DescontarInsumos`, sin consultar nada. */
export function validarComandoDescuento(
  datos: unknown,
  sobre: { version: unknown; idCorrelacion: string },
): ValidacionDescuento {
  const registro = (datos ?? {}) as Record<string, unknown>;
  const idSaga = esUuid(registro.idSaga) ? registro.idSaga : null;
  const idLabor = esUuid(registro.idLabor) ? registro.idLabor : null;
  const invalido = (motivo: string, insumosAfectados: InsumoAfectado[] = []): ValidacionDescuento => ({
    valido: false,
    motivo,
    idSaga,
    idLabor,
    insumosAfectados,
  });

  if (sobre.version !== 1) {
    return invalido(`Versión de mensaje no soportada: ${String(sobre.version)}.`);
  }
  if (idSaga === null || idLabor === null) {
    return invalido('idSaga e idLabor deben ser UUID.');
  }
  if (sobre.idCorrelacion !== idSaga) {
    return invalido('idCorrelacion debe ser igual a idSaga.');
  }
  if (!Array.isArray(registro.items) || registro.items.length === 0) {
    return invalido('items debe tener al menos un elemento.');
  }

  const vistos = new Set<string>();
  const afectados: InsumoAfectado[] = [];
  const items: ItemComandoDescuento[] = [];
  for (const item of registro.items as unknown[]) {
    const { idInsumo, cantidad } = (item ?? {}) as Record<string, unknown>;
    const cantidadTexto = typeof cantidad === 'string' ? cantidad : String(cantidad);
    // Mayor a 0: algún dígito distinto de cero (sin pasar por number).
    const cantidadValida =
      typeof cantidad === 'string' && PATRON_CANTIDAD.test(cantidad) && /[1-9]/.test(cantidad);
    if (!esUuid(idInsumo) || !cantidadValida || vistos.has(idInsumo)) {
      afectados.push({
        idInsumo: typeof idInsumo === 'string' ? idInsumo : String(idInsumo),
        cantidadSolicitada: cantidadTexto,
        stockDisponible: null,
      });
      continue;
    }
    vistos.add(idInsumo);
    items.push({ idInsumo, cantidad });
  }
  if (afectados.length > 0) {
    return invalido(
      'Cada ítem necesita un idInsumo UUID sin repetir y una cantidad en texto, mayor a 0, con hasta 3 decimales.',
      afectados,
    );
  }
  return { valido: true, comando: { idSaga, idLabor, items } };
}
