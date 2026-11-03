<?php

namespace App\Application\UseCases\QueryIncidents;

use App\Application\Contracts\UrlTemporal;
use App\Domain\Incident\Incidencia;

final class IncidenciaConFoto
{
    public function __construct(
        public readonly Incidencia $incidencia,
        public readonly UrlTemporal $foto,
    ) {}
}
