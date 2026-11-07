/** Configuración por variables de entorno (RNF-03, spec-consultas.md 2.2). */
export interface Configuracion {
  puerto: number;
  apiGatewayUrl: string;
  keycloakJwksUri: string;
  keycloakIssuer: string;
  keycloakAudience: string;
  keycloakTokenUrl: string;
  keycloakClientId: string;
  keycloakClientSecret: string;
  tiempoLimiteLlamadaMs: number;
  plazoConsultaMs: number;
  maximoLlamadas: number;
  produccion: boolean;
}

/** Constantes del plan (2.2): no son variables de entorno. */
export const TAMANIO_MAXIMO_PAGINA = 50;
export const TIEMPO_LIMITE_JWKS_MS = 1500;
export const TIEMPO_LIMITE_TOKEN_SERVICIO_MS = 2000;

export function leerConfiguracion(entorno: NodeJS.ProcessEnv = process.env): Configuracion {
  const obligatoria = (nombre: string): string => {
    const valor = entorno[nombre]?.trim();
    if (!valor) {
      throw new Error(`Falta la variable de entorno ${nombre}`);
    }
    return valor;
  };
  const entera = (nombre: string, porDefecto: number): number => {
    const texto = entorno[nombre]?.trim();
    if (!texto) {
      return porDefecto;
    }
    const valor = Number(texto);
    if (!Number.isInteger(valor) || valor <= 0) {
      throw new Error(`La variable de entorno ${nombre} debe ser un entero positivo`);
    }
    return valor;
  };

  const plazoConsultaMs = entera('GRAPHQL_PLAZO_CONSULTA_MS', 4500);
  if (plazoConsultaMs >= 5000) {
    throw new Error('GRAPHQL_PLAZO_CONSULTA_MS debe ser menor que 5000 (RNF-05)');
  }

  return {
    puerto: entera('PORT', 4000),
    apiGatewayUrl: obligatoria('API_GATEWAY_URL').replace(/\/+$/, ''),
    keycloakJwksUri: obligatoria('KEYCLOAK_JWKS_URI'),
    keycloakIssuer: obligatoria('KEYCLOAK_ISSUER'),
    keycloakAudience: obligatoria('KEYCLOAK_AUDIENCE'),
    keycloakTokenUrl: obligatoria('KEYCLOAK_TOKEN_URL'),
    keycloakClientId: obligatoria('KEYCLOAK_CLIENT_ID'),
    keycloakClientSecret: obligatoria('KEYCLOAK_CLIENT_SECRET'),
    tiempoLimiteLlamadaMs: entera('GRAPHQL_TIEMPO_LIMITE_LLAMADA_MS', 4000),
    plazoConsultaMs,
    maximoLlamadas: entera('GRAPHQL_MAXIMO_LLAMADAS', 200),
    produccion: entorno.NODE_ENV === 'production',
  };
}
