export const TIPOS_COMANDO = ['DescontarInsumos', 'RestaurarInsumos'] as const;
export type TipoComando = (typeof TIPOS_COMANDO)[number];

/** Sobre común de un comando recibido (constitución §8). */
export interface SobreComando {
  idMensaje: string;
  idCorrelacion: string;
  tipo: TipoComando;
  version: unknown;
  fechaOcurrencia: unknown;
  origen: string;
  datos: unknown;
}

/** El mensaje no se puede interpretar: va a la Dead Letter Queue sin reintentos. */
export class SobreInvalido extends Error {
  constructor(mensaje: string) {
    super(mensaje);
    this.name = 'SobreInvalido';
  }
}

const esTextoNoVacio = (valor: unknown): valor is string =>
  typeof valor === 'string' && valor.trim().length > 0;

export function interpretarSobre(contenido: Buffer): SobreComando {
  let crudo: unknown;
  try {
    crudo = JSON.parse(contenido.toString('utf8'));
  } catch {
    throw new SobreInvalido('El mensaje no es JSON válido.');
  }
  const sobre = (crudo ?? {}) as Record<string, unknown>;
  if (!esTextoNoVacio(sobre.idMensaje) || !esTextoNoVacio(sobre.idCorrelacion)) {
    throw new SobreInvalido('Faltan idMensaje o idCorrelacion en el sobre.');
  }
  if (!TIPOS_COMANDO.includes(sobre.tipo as TipoComando)) {
    throw new SobreInvalido(`Tipo de comando desconocido: ${String(sobre.tipo)}.`);
  }
  return {
    idMensaje: sobre.idMensaje,
    idCorrelacion: sobre.idCorrelacion,
    tipo: sobre.tipo as TipoComando,
    version: sobre.version,
    fechaOcurrencia: sobre.fechaOcurrencia,
    origen: esTextoNoVacio(sobre.origen) ? sobre.origen : 'desconocido',
    datos: sobre.datos,
  };
}
