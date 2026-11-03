<?php

namespace App\InterfaceAdapters\Console;

use App\Application\UseCases\Saga\ReanudarSagasEstancadas;
use Illuminate\Console\Command;

final class ReanudarSagasComando extends Command
{
    protected $signature = 'sagas:reanudar';

    protected $description = 'Reenvía o compensa las Sagas cuya fecha límite venció (spec-saga.md RQ-SAG-09).';

    public function handle(ReanudarSagasEstancadas $reanudar): int
    {
        $atendidas = $reanudar->ejecutar();
        if ($atendidas > 0) {
            $this->info("Sagas reanudadas: {$atendidas}");
        }

        return self::SUCCESS;
    }
}
