<?php

namespace App\InterfaceAdapters\Console;

use App\Application\UseCases\Saga\IniciarSagasPendientes;
use Illuminate\Console\Command;

final class IniciarSagasPendientesComando extends Command
{
    protected $signature = 'sagas:iniciar-pendientes';

    protected $description = 'Inicia la Saga de las labores PENDIENTE con insumos registradas antes de existir la Saga (se corre una vez al desplegar).';

    public function handle(IniciarSagasPendientes $iniciar): int
    {
        $this->info('Sagas iniciadas: '.$iniciar->ejecutar());

        return self::SUCCESS;
    }
}
