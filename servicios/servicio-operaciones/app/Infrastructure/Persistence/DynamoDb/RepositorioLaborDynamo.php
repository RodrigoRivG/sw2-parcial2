<?php

namespace App\Infrastructure\Persistence\DynamoDb;

use App\Application\Contracts\ConsultaLabores;
use App\Application\Contracts\Pagina;
use App\Application\UseCases\QueryFieldTasks\FiltroLabores;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\RepositorioLabor;
use App\Infrastructure\Persistence\DynamoDb\Mappers\LaborMapper;
use Aws\DynamoDb\DynamoDbClient;
use Aws\DynamoDb\Marshaler;
use DateTimeImmutable;

/**
 * Tabla `labores` y sus índices (spec-labores.md 2.3).
 */
final class RepositorioLaborDynamo implements ConsultaLabores, RepositorioLabor
{
    private readonly Marshaler $marshaler;

    public function __construct(
        private readonly DynamoDbClient $cliente,
        private readonly UnidadTrabajoDynamo $unidadTrabajo,
        private readonly NombresTablas $tablas,
    ) {
        $this->marshaler = new Marshaler;
    }

    public function buscar(string $id): ?LaborAgricola
    {
        $resultado = $this->cliente->getItem([
            'TableName' => $this->tabla(),
            'Key' => ['id' => ['S' => $id]],
            'ConsistentRead' => true,
        ]);

        return isset($resultado['Item']) ? LaborMapper::aLabor($this->marshaler->unmarshalItem($resultado['Item'])) : null;
    }

    public function guardarNueva(LaborAgricola $labor): void
    {
        $this->unidadTrabajo->agregar([
            'Put' => [
                'TableName' => $this->tabla(),
                'Item' => $this->marshaler->marshalItem(LaborMapper::aItem($labor)),
                'ConditionExpression' => 'attribute_not_exists(id)',
            ],
        ], 'labor');
    }

    public function actualizar(LaborAgricola $labor, int $versionLeida, ?EstadoLabor $estadoEsperado = null): void
    {
        $condicion = 'attribute_exists(id) AND #version = :version';
        $valores = [':version' => ['N' => (string) $versionLeida]];
        if ($estadoEsperado !== null) {
            $condicion .= ' AND #estado = :estado';
            $valores[':estado'] = ['S' => $estadoEsperado->value];
        }

        $this->unidadTrabajo->agregar([
            'Put' => [
                'TableName' => $this->tabla(),
                'Item' => $this->marshaler->marshalItem(LaborMapper::aItem($labor)),
                'ConditionExpression' => $condicion,
                'ExpressionAttributeNames' => ['#version' => 'version'] + ($estadoEsperado !== null ? ['#estado' => 'estado'] : []),
                'ExpressionAttributeValues' => $valores,
            ],
        ], 'labor');
    }

    public function conValidacionVencida(DateTimeImmutable $ahora, int $maximo): array
    {
        $resultado = $this->cliente->query([
            'TableName' => $this->tabla(),
            'IndexName' => 'gsi_validacion_pendiente',
            'KeyConditionExpression' => 'validacion_pendiente = :pendiente AND fecha_proximo_validacion <= :ahora',
            'ExpressionAttributeValues' => [
                ':pendiente' => ['S' => '1'],
                ':ahora' => ['S' => FormatoFecha::conHora($ahora)],
            ],
            'Limit' => $maximo,
        ]);

        return array_map(fn (array $item) => LaborMapper::aLabor($this->marshaler->unmarshalItem($item)), $resultado['Items'] ?? []);
    }

    public function pendientesSinSaga(int $maximo): array
    {
        $labores = [];
        $parametros = [
            'TableName' => $this->tabla(),
            'IndexName' => 'gsi_estado',
            'KeyConditionExpression' => 'estado = :pendiente',
            'FilterExpression' => 'attribute_not_exists(id_saga) AND validacion_campania = :validada AND size(insumos) > :cero',
            'ExpressionAttributeValues' => [':pendiente' => ['S' => 'PENDIENTE'], ':validada' => ['S' => 'VALIDADA'], ':cero' => ['N' => '0']],
        ];
        do {
            $resultado = $this->cliente->query($parametros);
            foreach ($resultado['Items'] ?? [] as $item) {
                $labores[] = LaborMapper::aLabor($this->marshaler->unmarshalItem($item));
            }
            $parametros['ExclusiveStartKey'] = $resultado['LastEvaluatedKey'] ?? null;
        } while ($parametros['ExclusiveStartKey'] !== null && count($labores) < $maximo);

        return array_slice($labores, 0, $maximo);
    }

    public function listar(FiltroLabores $filtro): Pagina
    {
        // El primer filtro presente elige el índice; los demás van en FilterExpression (spec-labores.md 2.3)
        [$indice, $particion, $valorParticion] = match (true) {
            $filtro->idCampania !== null => ['gsi_campania', 'id_campania', $filtro->idCampania],
            $filtro->idResponsable !== null => ['gsi_responsable', 'id_responsable', $filtro->idResponsable],
            default => ['gsi_estado', 'estado', $filtro->estado?->value ?? ''],
        };

        $nombres = ['#p' => $particion];
        $valores = [':p' => ['S' => $valorParticion]];
        $condicionClave = '#p = :p';

        if ($filtro->fechaDesde !== null || $filtro->fechaHasta !== null) {
            $nombres['#f'] = 'fecha_referencia';
            $valores[':desde'] = ['S' => $filtro->fechaDesde ?? '0000-00-00'];
            // "2026-11-20" < "2026-11-20T23:59:59Z" < "2026-11-20T99": incluye todo el día "hasta"
            $valores[':hasta'] = ['S' => ($filtro->fechaHasta ?? '9999-12-31').'T99'];
            $condicionClave .= ' AND #f BETWEEN :desde AND :hasta';
        }

        $filtros = [];
        foreach (['id_campania' => $filtro->idCampania, 'id_responsable' => $filtro->idResponsable, 'estado' => $filtro->estado?->value] as $atributo => $valor) {
            if ($valor !== null && $atributo !== $particion) {
                $nombres["#{$atributo}"] = $atributo;
                $valores[":{$atributo}"] = ['S' => $valor];
                $filtros[] = "#{$atributo} = :{$atributo}";
            }
        }

        $parametros = [
            'TableName' => $this->tabla(),
            'IndexName' => $indice,
            'KeyConditionExpression' => $condicionClave,
            'ExpressionAttributeNames' => $nombres,
            'ExpressionAttributeValues' => $valores,
            'ScanIndexForward' => $filtro->ascendente,
            'Limit' => $filtro->limite,
        ];
        if ($filtros !== []) {
            $parametros['FilterExpression'] = implode(' AND ', $filtros);
        }
        if ($filtro->cursor !== null) {
            $parametros['ExclusiveStartKey'] = CodificadorCursor::decodificar(
                $filtro->cursor,
                ['id', $particion, 'fecha_referencia'],
                [$particion => $valorParticion],
            );
        }

        $resultado = $this->cliente->query($parametros);

        return new Pagina(
            array_map(fn (array $item) => LaborMapper::aLabor($this->marshaler->unmarshalItem($item)), $resultado['Items'] ?? []),
            CodificadorCursor::codificar($resultado['LastEvaluatedKey'] ?? null),
        );
    }

    private function tabla(): string
    {
        return $this->tablas->de('labores');
    }
}
