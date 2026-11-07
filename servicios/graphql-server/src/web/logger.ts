/** Logs JSON de una línea en la salida estándar, como los demás servicios (constitución §7). */
type Nivel = 'INFO' | 'WARN' | 'ERROR';

function escribir(nivel: Nivel, mensaje: string, campos: Record<string, unknown>): void {
  const linea = JSON.stringify({ fecha: new Date().toISOString(), nivel, logger: 'graphql-server', mensaje, ...campos });
  process.stdout.write(`${linea}\n`);
}

export const logger = {
  info: (mensaje: string, campos: Record<string, unknown> = {}) => escribir('INFO', mensaje, campos),
  warn: (mensaje: string, campos: Record<string, unknown> = {}) => escribir('WARN', mensaje, campos),
  error: (mensaje: string, campos: Record<string, unknown> = {}) => escribir('ERROR', mensaje, campos),
};
