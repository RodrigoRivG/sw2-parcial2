<?php

namespace App\Infrastructure\Persistence\DynamoDb;

use App\InterfaceAdapters\Http\Salud\ComprobacionSalud;
use Aws\DynamoDb\DynamoDbClient;

final class ComprobacionDynamoDb implements ComprobacionSalud
{
    public function __construct(
        private readonly DynamoDbClient $cliente,
        private readonly NombresTablas $tablas,
    ) {}

    public function nombre(): string
    {
        return 'dynamodb';
    }

    public function comprobar(): void
    {
        $this->cliente->describeTable(['TableName' => $this->tablas->de('labores')]);
    }
}
