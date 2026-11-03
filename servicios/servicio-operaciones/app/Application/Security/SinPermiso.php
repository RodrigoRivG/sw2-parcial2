<?php

namespace App\Application\Security;

use RuntimeException;

/**
 * El usuario no tiene el rol que exige la operación (RN-16). Lo lanzan el middleware de roles
 * y los casos de uso cuyas reglas dependen del cuerpo o del recurso.
 */
final class SinPermiso extends RuntimeException
{
    public function __construct(string $mensaje = 'No tiene permiso para realizar esta operación.')
    {
        parent::__construct($mensaje);
    }
}
