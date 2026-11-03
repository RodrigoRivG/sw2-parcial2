<?php

namespace App\Application\UseCases\RegisterIncident;

use App\Domain\Incident\Incidencia;

final class ResultadoIncidencia
{
    public function __construct(
        public readonly Incidencia $incidencia,
        public readonly bool $repetida,
    ) {}
}
