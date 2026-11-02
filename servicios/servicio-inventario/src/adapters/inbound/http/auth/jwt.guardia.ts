import {
  CanActivate,
  ExecutionContext,
  Inject,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { JWTPayload, JWTVerifyGetKey, jwtVerify } from 'jose';
import { CONFIGURACION, Configuracion } from '../../../../config/validacion-entorno';
import { CLAVE_PUBLICA, SolicitudAutenticada } from './decoradores';

/** Claves públicas de Keycloak (JWKS). En los tests se reemplaza por un conjunto local. */
export const CONJUNTO_CLAVES = 'CONJUNTO_CLAVES';

/** Valida firma, emisor, audiencia y vigencia del JWT en cada solicitud (RNF-02). */
@Injectable()
export class JwtGuardia implements CanActivate {
  constructor(
    private readonly reflector: Reflector,
    @Inject(CONJUNTO_CLAVES) private readonly claves: JWTVerifyGetKey,
    @Inject(CONFIGURACION) private readonly configuracion: Configuracion,
  ) {}

  async canActivate(contexto: ExecutionContext): Promise<boolean> {
    const publica = this.reflector.getAllAndOverride<boolean>(CLAVE_PUBLICA, [
      contexto.getHandler(),
      contexto.getClass(),
    ]);
    if (publica) {
      return true;
    }
    const solicitud = contexto.switchToHttp().getRequest<SolicitudAutenticada>();
    const token = extraerToken(solicitud.headers.authorization);
    if (!token) {
      throw new UnauthorizedException();
    }
    try {
      const { payload } = await jwtVerify(token, this.claves, {
        issuer: this.configuracion.keycloakIssuer,
        audience: this.configuracion.keycloakAudience,
        requiredClaims: ['sub', 'exp'],
      });
      solicitud.usuario = { sub: payload.sub as string, roles: extraerRoles(payload) };
      return true;
    } catch {
      throw new UnauthorizedException();
    }
  }
}

function extraerToken(encabezado: string | string[] | undefined): string | null {
  if (typeof encabezado !== 'string') {
    return null;
  }
  const [esquema, token] = encabezado.split(' ');
  return esquema?.toLowerCase() === 'bearer' && token ? token : null;
}

/** Roles de realm de Keycloak (`realm_access.roles`). */
function extraerRoles(payload: JWTPayload): string[] {
  const roles = (payload.realm_access as { roles?: unknown } | undefined)?.roles;
  return Array.isArray(roles) ? roles.filter((rol): rol is string => typeof rol === 'string') : [];
}
