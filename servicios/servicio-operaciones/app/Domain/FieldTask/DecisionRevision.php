<?php

namespace App\Domain\FieldTask;

enum DecisionRevision: string
{
    case CONFIRMAR = 'CONFIRMAR';
    case RECHAZAR = 'RECHAZAR';
    case REINTENTAR = 'REINTENTAR';
}
