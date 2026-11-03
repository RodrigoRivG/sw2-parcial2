<?php

namespace App\Domain\Shared;

enum TipoErrorDominio: string
{
    case NO_ENCONTRADO = 'NO_ENCONTRADO';
    case CONFLICTO = 'CONFLICTO';
    case REGLA_NEGOCIO = 'REGLA_NEGOCIO';
}
