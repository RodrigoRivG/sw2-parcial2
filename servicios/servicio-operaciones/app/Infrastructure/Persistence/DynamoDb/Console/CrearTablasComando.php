<?php

namespace App\Infrastructure\Persistence\DynamoDb\Console;

use App\Infrastructure\Persistence\DynamoDb\CreadorTablas;
use Illuminate\Console\Command;

/**
 * Vive en Infrastructure (no en InterfaceAdapters/Console) porque solo maneja el esquema de DynamoDB.
 */
final class CrearTablasComando extends Command
{
    protected $signature = 'dynamodb:crear-tablas';

    protected $description = 'Crea las tablas e índices de DynamoDB que faltan (idempotente).';

    public function handle(CreadorTablas $creador): int
    {
        $creadas = $creador->crearFaltantes();
        $this->info($creadas === [] ? 'Las tablas ya existen.' : 'Tablas creadas: '.implode(', ', $creadas));

        return self::SUCCESS;
    }
}
