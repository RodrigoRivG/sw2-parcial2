<?php

namespace App\Domain\FieldTask;

enum EstadoLabor: string
{
    case PROGRAMADA = 'PROGRAMADA';
    case PENDIENTE = 'PENDIENTE';
    case CONFIRMADA = 'CONFIRMADA';
    case RECHAZADA = 'RECHAZADA';
    case PENDIENTE_REVISION = 'PENDIENTE_REVISION';
}
