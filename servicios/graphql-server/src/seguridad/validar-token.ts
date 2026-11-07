import { createRemoteJWKSet, errors, jwtVerify, type JWTPayload, type JWTVerifyGetKey } from 'jose';
import { TIEMPO_LIMITE_JWKS_MS, type Configuracion } from '../config';

export interface Usuario {
  sub: string;
  roles: string[];
}

/** No se pudieron obtener las claves de Keycloak: es un 503, no un 401 (casos borde de la spec). */
export class ClavesNoDisponibles extends Error {}

export type ValidadorToken = (token: string) => Promise<Usuario>;

/** Valida firma, `iss`, `aud` y `exp` (RNF-02). La descarga del JWKS tiene su propio tiempo límite (2.5). */
export function crearValidadorToken(configuracion: Configuracion): ValidadorToken {
  const remoto = createRemoteJWKSet(new URL(configuracion.keycloakJwksUri), { timeoutDuration: TIEMPO_LIMITE_JWKS_MS });
  const claves: JWTVerifyGetKey = async (encabezado, token) => {
    try {
      return await remoto(encabezado, token);
    } catch (error) {
      // Un kid desconocido es un token inválido; cualquier otra falla es Keycloak no disponible.
      if (error instanceof errors.JWKSNoMatchingKey || error instanceof errors.JWKSMultipleMatchingKeys) {
        throw error;
      }
      throw new ClavesNoDisponibles();
    }
  };

  return async (token) => {
    const { payload } = await jwtVerify(token, claves, {
      issuer: configuracion.keycloakIssuer,
      audience: configuracion.keycloakAudience,
      requiredClaims: ['sub', 'exp'],
    });
    return { sub: payload.sub as string, roles: extraerRoles(payload) };
  };
}

function extraerRoles(payload: JWTPayload): string[] {
  const roles = (payload.realm_access as { roles?: unknown } | undefined)?.roles;
  return Array.isArray(roles) ? roles.filter((rol): rol is string => typeof rol === 'string') : [];
}
