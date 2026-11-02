export const CONFIGURACION = 'CONFIGURACION';

export interface Configuracion {
  puerto: number;
  mongodbUri: string;
  keycloakIssuer: string;
  keycloakJwksUri: string;
  keycloakAudience: string;
}

const REQUERIDAS = [
  'PORT',
  'MONGODB_URI',
  'KEYCLOAK_ISSUER',
  'KEYCLOAK_JWKS_URI',
  'KEYCLOAK_AUDIENCE',
] as const;

/** Lee y valida las variables de entorno. Si falta alguna, el servicio no arranca. */
export function leerConfiguracion(entorno: NodeJS.ProcessEnv = process.env): Configuracion {
  const faltantes = REQUERIDAS.filter((nombre) => !entorno[nombre]?.trim());
  if (faltantes.length > 0) {
    throw new Error(`Faltan variables de entorno: ${faltantes.join(', ')}`);
  }
  const puerto = Number(entorno.PORT);
  if (!Number.isInteger(puerto) || puerto <= 0) {
    throw new Error('PORT debe ser un número de puerto válido.');
  }
  return {
    puerto,
    mongodbUri: entorno.MONGODB_URI as string,
    keycloakIssuer: entorno.KEYCLOAK_ISSUER as string,
    keycloakJwksUri: entorno.KEYCLOAK_JWKS_URI as string,
    keycloakAudience: entorno.KEYCLOAK_AUDIENCE as string,
  };
}
