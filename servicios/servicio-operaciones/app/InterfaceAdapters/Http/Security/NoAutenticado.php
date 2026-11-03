<?php

namespace App\InterfaceAdapters\Http\Security;

use RuntimeException;

final class NoAutenticado extends RuntimeException
{
    public function __construct(string $motivo = 'Token ausente o inválido.')
    {
        parent::__construct($motivo);
    }
}
