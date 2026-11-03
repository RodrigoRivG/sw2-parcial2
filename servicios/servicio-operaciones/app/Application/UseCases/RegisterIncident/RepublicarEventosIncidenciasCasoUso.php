<?php

namespace App\Application\UseCases\RegisterIncident;

use App\Application\Contracts\Reloj;
use App\Domain\Incident\RepositorioIncidencia;
use App\Domain\Shared\Uuid;

/**
 * Tarea programada: republica los eventos que el broker no confirmó (spec-incidencias.md RQ-INC-08).
 * Solo toma las que llevan más de 1 minuto pendientes, para no competir con la solicitud que las está publicando.
 */
final class RepublicarEventosIncidenciasCasoUso
{
    private const SEGUNDOS_DE_GRACIA = 60;

    private const MAXIMO_POR_EJECUCION = 100;

    public function __construct(
        private readonly RepositorioIncidencia $repositorio,
        private readonly NotificacionIncidencia $notificacion,
        private readonly Reloj $reloj,
    ) {}

    /** @return int eventos publicados */
    public function ejecutar(): int
    {
        $antesDe = $this->reloj->ahora()->modify('-'.self::SEGUNDOS_DE_GRACIA.' seconds');
        $publicados = 0;
        foreach ($this->repositorio->pendientesDeNotificar($antesDe, self::MAXIMO_POR_EJECUCION) as $incidencia) {
            if ($this->notificacion->notificar($incidencia, Uuid::v4())) {
                $publicados++;
            }
        }

        return $publicados;
    }
}
