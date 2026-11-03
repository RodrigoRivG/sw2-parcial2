<?php

namespace App\Domain\Incident;

enum TipoIncidencia: string
{
    case PLAGA = 'PLAGA';
    case ENFERMEDAD = 'ENFERMEDAD';
    case DANIO = 'DANIO';
    case OTRO = 'OTRO';
}
