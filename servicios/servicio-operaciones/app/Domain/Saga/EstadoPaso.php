<?php

namespace App\Domain\Saga;

enum EstadoPaso: string
{
    case ENVIADO = 'ENVIADO';
    case COMPLETADO = 'COMPLETADO';
    case RECHAZADO = 'RECHAZADO';
    case OMITIDO = 'OMITIDO';
    case SIN_RESPUESTA = 'SIN_RESPUESTA';
}
