<?php

namespace App\Domain\FieldTask;

enum TipoLabor: string
{
    case PREPARACION_SUELO = 'PREPARACION_SUELO';
    case SIEMBRA = 'SIEMBRA';
    case FERTILIZACION = 'FERTILIZACION';
    case RIEGO = 'RIEGO';
    case CONTROL_FITOSANITARIO = 'CONTROL_FITOSANITARIO';
    case DESHIERBE = 'DESHIERBE';
    case COSECHA = 'COSECHA';
    case OTRA = 'OTRA';
}
