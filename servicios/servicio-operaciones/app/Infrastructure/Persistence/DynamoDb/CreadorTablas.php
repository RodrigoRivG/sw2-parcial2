<?php

namespace App\Infrastructure\Persistence\DynamoDb;

use Aws\DynamoDb\DynamoDbClient;
use Aws\DynamoDb\Exception\DynamoDbException;
use RuntimeException;

/**
 * Crea las tablas de database/dynamodb/tablas.json que faltan. Es idempotente.
 */
final class CreadorTablas
{
    public function __construct(
        private readonly DynamoDbClient $cliente,
        private readonly NombresTablas $tablas,
        private readonly string $rutaDefinicion,
    ) {}

    /**
     * @return list<string> nombres de las tablas creadas
     */
    public function crearFaltantes(): array
    {
        $existentes = $this->listarExistentes();
        $creadas = [];

        foreach ($this->definiciones() as $definicion) {
            $nombre = $this->tablas->de($definicion['nombre']);
            if (in_array($nombre, $existentes, true)) {
                continue;
            }
            try {
                $this->cliente->createTable($this->parametros($nombre, $definicion));
            } catch (DynamoDbException $e) {
                // Otra instancia la creó al mismo tiempo
                if ($e->getAwsErrorCode() !== 'ResourceInUseException') {
                    throw $e;
                }
            }
            $creadas[] = $nombre;
        }

        foreach ($creadas as $nombre) {
            $this->cliente->waitUntil('TableExists', ['TableName' => $nombre]);
        }

        return $creadas;
    }

    /** Borra las tablas del prefijo actual. Solo para los tests. */
    public function eliminarTodas(): void
    {
        if ($this->tablas->prefijo() === '') {
            throw new RuntimeException('Sin prefijo no se borran tablas: serían las reales.');
        }
        $existentes = $this->listarExistentes();
        foreach ($this->definiciones() as $definicion) {
            $nombre = $this->tablas->de($definicion['nombre']);
            if (in_array($nombre, $existentes, true)) {
                $this->cliente->deleteTable(['TableName' => $nombre]);
            }
        }
    }

    /**
     * @return list<array{nombre: string, clave: string, indices: list<array{nombre: string, particion: string, orden: string}>}>
     */
    private function definiciones(): array
    {
        $contenido = json_decode((string) file_get_contents($this->rutaDefinicion), true, flags: JSON_THROW_ON_ERROR);

        return $contenido['tablas'];
    }

    /**
     * @return list<string>
     */
    private function listarExistentes(): array
    {
        $nombres = [];
        $parametros = [];
        do {
            $resultado = $this->cliente->listTables($parametros);
            array_push($nombres, ...($resultado['TableNames'] ?? []));
            $parametros = isset($resultado['LastEvaluatedTableName'])
                ? ['ExclusiveStartTableName' => $resultado['LastEvaluatedTableName']]
                : [];
        } while ($parametros !== []);

        return $nombres;
    }

    /**
     * @param  array{nombre: string, clave: string, indices: list<array{nombre: string, particion: string, orden: string}>}  $definicion
     * @return array<string, mixed>
     */
    private function parametros(string $nombre, array $definicion): array
    {
        $atributos = [$definicion['clave']];
        $indices = [];
        foreach ($definicion['indices'] as $indice) {
            $atributos[] = $indice['particion'];
            $atributos[] = $indice['orden'];
            $indices[] = [
                'IndexName' => $indice['nombre'],
                'KeySchema' => [
                    ['AttributeName' => $indice['particion'], 'KeyType' => 'HASH'],
                    ['AttributeName' => $indice['orden'], 'KeyType' => 'RANGE'],
                ],
                'Projection' => ['ProjectionType' => 'ALL'],
            ];
        }

        $parametros = [
            'TableName' => $nombre,
            'BillingMode' => 'PAY_PER_REQUEST',
            'KeySchema' => [['AttributeName' => $definicion['clave'], 'KeyType' => 'HASH']],
            'AttributeDefinitions' => array_map(
                fn (string $atributo) => ['AttributeName' => $atributo, 'AttributeType' => 'S'],
                array_values(array_unique($atributos)),
            ),
        ];
        if ($indices !== []) {
            $parametros['GlobalSecondaryIndexes'] = $indices;
        }

        return $parametros;
    }
}
