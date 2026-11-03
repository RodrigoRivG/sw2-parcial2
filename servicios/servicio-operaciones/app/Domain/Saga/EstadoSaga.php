<?php

namespace App\Domain\Saga;

enum EstadoSaga: string
{
    case EN_CURSO = 'EN_CURSO';
    case COMPENSANDO = 'COMPENSANDO';
    case COMPLETADA = 'COMPLETADA';
    case RECHAZADA = 'RECHAZADA';
    case COMPENSADA = 'COMPENSADA';
    case REQUIERE_INTERVENCION = 'REQUIERE_INTERVENCION';

    public function activa(): bool
    {
        return $this === self::EN_CURSO || $this === self::COMPENSANDO;
    }
}
