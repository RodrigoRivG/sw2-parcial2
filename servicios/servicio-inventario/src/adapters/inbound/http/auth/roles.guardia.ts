import { CanActivate, ExecutionContext, ForbiddenException, Injectable } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { CLAVE_PUBLICA, CLAVE_ROLES, Rol, SolicitudAutenticada } from './decoradores';

/** Exige alguno de los roles de `@Roles`. Una ruta sin `@Roles` ni `@Publica` queda prohibida. */
@Injectable()
export class RolesGuardia implements CanActivate {
  constructor(private readonly reflector: Reflector) {}

  canActivate(contexto: ExecutionContext): boolean {
    const objetivos = [contexto.getHandler(), contexto.getClass()];
    if (this.reflector.getAllAndOverride<boolean>(CLAVE_PUBLICA, objetivos)) {
      return true;
    }
    const permitidos = this.reflector.getAllAndOverride<Rol[]>(CLAVE_ROLES, objetivos) ?? [];
    const roles = contexto.switchToHttp().getRequest<SolicitudAutenticada>().usuario?.roles ?? [];
    if (!roles.some((rol) => (permitidos as string[]).includes(rol))) {
      throw new ForbiddenException();
    }
    return true;
  }
}
