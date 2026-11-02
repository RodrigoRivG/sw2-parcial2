import { ExecutionContext, SetMetadata, createParamDecorator } from '@nestjs/common';

export type Rol = 'administrador' | 'gerencia' | 'tecnico_campo' | 'lectura_inventario';

export interface UsuarioAutenticado {
  /** `sub` del token: usuario o cuenta de servicio. */
  sub: string;
  roles: string[];
}

export interface SolicitudAutenticada {
  headers: Record<string, string | string[] | undefined>;
  usuario?: UsuarioAutenticado;
}

export const CLAVE_PUBLICA = 'publica';
export const CLAVE_ROLES = 'roles';

/** Ruta sin token (salud). */
export const Publica = () => SetMetadata(CLAVE_PUBLICA, true);

/** Roles de realm que permiten la operación; basta con tener uno. */
export const Roles = (...roles: Rol[]) => SetMetadata(CLAVE_ROLES, roles);

export const UsuarioActual = createParamDecorator(
  (_dato: unknown, contexto: ExecutionContext): UsuarioAutenticado => {
    const usuario = contexto.switchToHttp().getRequest<SolicitudAutenticada>().usuario;
    if (!usuario) {
      throw new Error('UsuarioActual se usó en una ruta sin autenticación.');
    }
    return usuario;
  },
);
