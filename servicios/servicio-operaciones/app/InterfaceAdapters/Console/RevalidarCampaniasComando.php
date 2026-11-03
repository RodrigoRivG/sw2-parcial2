<?php

namespace App\InterfaceAdapters\Console;

use App\Application\UseCases\RevalidateCampaign\RevalidarCampaniasCasoUso;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Context;
use Illuminate\Support\Str;

final class RevalidarCampaniasComando extends Command
{
    protected $signature = 'labores:revalidar-campanias';

    protected $description = 'Revalida las labores cuya consulta de campaña quedó diferida (spec-labores.md RQ-LAB-10).';

    public function handle(RevalidarCampaniasCasoUso $revalidar): int
    {
        Context::add('idCorrelacion', (string) Str::uuid());
        $resumen = $revalidar->ejecutar();
        if (array_sum($resumen) > 0) {
            $this->info(sprintf('Validadas: %d · rechazadas: %d · pospuestas: %d', $resumen['validadas'], $resumen['rechazadas'], $resumen['pospuestas']));
        }

        return self::SUCCESS;
    }
}
