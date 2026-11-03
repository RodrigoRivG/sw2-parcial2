<?php

namespace App\Domain\Shared;

enum ResultadoSincronizacion: string
{
    case SINCRONIZADA = 'SINCRONIZADA';
    case ERROR = 'ERROR';
}
