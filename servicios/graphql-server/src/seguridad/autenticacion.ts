import type { RequestHandler } from 'express';
import { responderError } from '../web/errores';
import { ROLES_USUARIO } from './permisos';
import { ClavesNoDisponibles, type ValidadorToken } from './validar-token';

/**
 * Validación del token en /api/graphql, antes de Apollo (2.5): sin token válido, 401; sin administrador ni
 * gerencia, 403; sin claves de Keycloak, 503. Fuera de producción deja pasar el GET que pide HTML: Apollo solo
 * responde con la página de Sandbox, nunca ejecuta una consulta.
 */
export function autenticacion(validar: ValidadorToken, produccion: boolean): RequestHandler {
  return async (req, res, next) => {
    if (!produccion && req.method === 'GET' && req.accepts(['application/json', 'text/html']) === 'text/html') {
      next();
      return;
    }
    const [esquema, token] = (req.get('Authorization') ?? '').split(' ');
    if (esquema?.toLowerCase() !== 'bearer' || !token) {
      responderError(res, 'NO_AUTENTICADO');
      return;
    }
    try {
      res.locals.usuario = await validar(token);
    } catch (error) {
      responderError(res, error instanceof ClavesNoDisponibles ? 'AUTENTICACION_NO_DISPONIBLE' : 'NO_AUTENTICADO');
      return;
    }
    const roles: string[] = res.locals.usuario.roles;
    if (!roles.some((rol) => ROLES_USUARIO.includes(rol))) {
      responderError(res, 'SIN_PERMISO');
      return;
    }
    next();
  };
}
