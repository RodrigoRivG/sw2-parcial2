<?php

namespace App\Infrastructure\Persistence\DynamoDb;

use App\Domain\Saga\RepositorioSaga;
use App\Domain\Saga\Saga;
use App\Infrastructure\Persistence\DynamoDb\Mappers\SagaMapper;
use Aws\DynamoDb\DynamoDbClient;
use Aws\DynamoDb\Marshaler;
use DateTimeImmutable;

/**
 * Tabla `sagas` (spec-saga.md 2.6).
 */
final class RepositorioSagaDynamo implements RepositorioSaga
{
    private readonly Marshaler $marshaler;

    public function __construct(
        private readonly DynamoDbClient $cliente,
        private readonly UnidadTrabajoDynamo $unidadTrabajo,
        private readonly NombresTablas $tablas,
    ) {
        $this->marshaler = new Marshaler;
    }

    public function buscar(string $idSaga): ?Saga
    {
        $resultado = $this->cliente->getItem([
            'TableName' => $this->tabla(),
            'Key' => ['id_saga' => ['S' => $idSaga]],
            'ConsistentRead' => true,
        ]);

        return isset($resultado['Item']) ? SagaMapper::aSaga($this->marshaler->unmarshalItem($resultado['Item'])) : null;
    }

    public function guardarNueva(Saga $saga): void
    {
        $this->unidadTrabajo->agregar([
            'Put' => [
                'TableName' => $this->tabla(),
                'Item' => $this->marshaler->marshalItem(SagaMapper::aItem($saga)),
                'ConditionExpression' => 'attribute_not_exists(id_saga)',
            ],
        ], 'saga');
    }

    public function actualizar(Saga $saga, int $versionLeida): void
    {
        $this->unidadTrabajo->agregar([
            'Put' => [
                'TableName' => $this->tabla(),
                'Item' => $this->marshaler->marshalItem(SagaMapper::aItem($saga)),
                'ConditionExpression' => 'attribute_exists(id_saga) AND #version = :version',
                'ExpressionAttributeNames' => ['#version' => 'version'],
                'ExpressionAttributeValues' => [':version' => ['N' => (string) $versionLeida]],
            ],
        ], 'saga');
    }

    public function vencidas(DateTimeImmutable $ahora, int $maximo): array
    {
        $resultado = $this->cliente->query([
            'TableName' => $this->tabla(),
            'IndexName' => 'gsi_activas',
            'KeyConditionExpression' => 'activa = :activa AND fecha_limite <= :ahora',
            'ExpressionAttributeValues' => [':activa' => ['S' => '1'], ':ahora' => ['S' => FormatoFecha::conHora($ahora)]],
            'ProjectionExpression' => 'id_saga',
            'Limit' => $maximo,
        ]);

        return array_map(fn (array $item) => $item['id_saga']['S'], $resultado['Items'] ?? []);
    }

    private function tabla(): string
    {
        return $this->tablas->de('sagas');
    }
}
