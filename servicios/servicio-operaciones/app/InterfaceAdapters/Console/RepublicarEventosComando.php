<?php

namespace App\InterfaceAdapters\Console;

use App\Application\UseCases\RegisterIncident\RepublicarEventosIncidenciasCasoUso;
use Illuminate\Console\Command;

final class RepublicarEventosComando extends Command
{
    protected $signature = 'incidencias:republicar-eventos';

    protected $description = 'Republica los eventos IncidenciaRegistrada que el broker no confirmó (spec-incidencias.md RQ-INC-08).';

    public function handle(RepublicarEventosIncidenciasCasoUso $republicar): int
    {
        $publicados = $republicar->ejecutar();
        if ($publicados > 0) {
            $this->info("Eventos republicados: {$publicados}");
        }

        return self::SUCCESS;
    }
}
