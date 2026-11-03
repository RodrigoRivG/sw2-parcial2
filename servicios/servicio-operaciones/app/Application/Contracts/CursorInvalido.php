<?php

namespace App\Application\Contracts;

use RuntimeException;

/** El cursor no se puede decodificar o es de otro listado: 400 DATOS_INVALIDOS. */
final class CursorInvalido extends RuntimeException
{
    public function __construct()
    {
        parent::__construct('El cursor no es válido para este listado.');
    }
}
