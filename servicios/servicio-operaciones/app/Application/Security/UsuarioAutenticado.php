<?php

namespace App\Application\Security;

/**
 * Usuario o cuenta de servicio del token ya validado. El responsable de una operación sale de aquí (README D-11).
 */
final class UsuarioAutenticado
{
    /**
     * @param  list<string>  $roles
     */
    public function __construct(
        public readonly string $id,
        public readonly string $nombre,
        public readonly array $roles,
    ) {}

    public function tieneRol(string ...$roles): bool
    {
        return array_intersect($roles, $this->roles) !== [];
    }
}
