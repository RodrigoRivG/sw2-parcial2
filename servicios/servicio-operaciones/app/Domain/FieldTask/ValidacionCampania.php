<?php

namespace App\Domain\FieldTask;

enum ValidacionCampania: string
{
    case VALIDADA = 'VALIDADA';
    /** servicio-gestion no respondió: la validación se reintenta (spec-labores.md RQ-LAB-09). */
    case PENDIENTE = 'PENDIENTE';
}
