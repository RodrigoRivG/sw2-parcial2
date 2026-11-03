<?php

namespace App\Infrastructure\Persistence\DynamoDb;

use App\Application\Contracts\ConsultaIncidencias;
use App\Application\Contracts\Pagina;
use App\Application\UseCases\QueryIncidents\FiltroIncidencias;
use App\Domain\Incident\Incidencia;
use App\Domain\Incident\RepositorioIncidencia;
use App\Infrastructure\Persistence\DynamoDb\Mappers\IncidenciaMapper;
use Aws\DynamoDb\DynamoDbClient;
use Aws\DynamoDb\Exception\DynamoDbException;
use Aws\DynamoDb\Marshaler;
use DateTimeImmutable;

/**
 * Tabla `incidencias` y sus índices (spec-incidencias.md 2.3).
 */
final class RepositorioIncidenciaDynamo implements ConsultaIncidencias, RepositorioIncidencia
{
    private readonly Marshaler $marshaler;

    public function __construct(
        private readonly DynamoDbClient $cliente,
        private readonly UnidadTrabajoDynamo $unidadTrabajo,
        private readonly NombresTablas $tablas,
    ) {
        $this->marshaler = new Marshaler;
    }

    public function buscar(string $id): ?Incidencia
    {
        $resultado = $this->cliente->getItem([
            'TableName' => $this->tabla(),
            'Key' => ['id' => ['S' => $id]],
            'ConsistentRead' => true,
        ]);

        return isset($resultado['Item']) ? IncidenciaMapper::aIncidencia($this->marshaler->unmarshalItem($resultado['Item'])) : null;
    }

    public function guardarNueva(Incidencia $incidencia): void
    {
        $this->unidadTrabajo->agregar([
            'Put' => [
                'TableName' => $this->tabla(),
                'Item' => $this->marshaler->marshalItem(IncidenciaMapper::aItem($incidencia)),
                'ConditionExpression' => 'attribute_not_exists(id)',
            ],
        ], 'incidencia');
    }

    public function marcarNotificada(string $id): void
    {
        try {
            $this->cliente->updateItem([
                'TableName' => $this->tabla(),
                'Key' => ['id' => ['S' => $id]],
                'UpdateExpression' => 'REMOVE notificacion_pendiente',
                'ConditionExpression' => 'attribute_exists(id)',
            ]);
        } catch (DynamoDbException $e) {
            if ($e->getAwsErrorCode() !== 'ConditionalCheckFailedException') {
                throw $e;
            }
        }
    }

    public function pendientesDeNotificar(DateTimeImmutable $antesDe, int $maximo): array
    {
        $resultado = $this->cliente->query([
            'TableName' => $this->tabla(),
            'IndexName' => 'gsi_notificacion_pendiente',
            'KeyConditionExpression' => 'notificacion_pendiente = :pendiente AND fecha_recepcion <= :antes',
            'ExpressionAttributeValues' => [':pendiente' => ['S' => '1'], ':antes' => ['S' => FormatoFecha::conHora($antesDe)]],
            'Limit' => $maximo,
        ]);

        return array_map(fn (array $item) => IncidenciaMapper::aIncidencia($this->marshaler->unmarshalItem($item)), $resultado['Items'] ?? []);
    }

    public function listar(FiltroIncidencias $filtro): Pagina
    {
        // El primer filtro presente elige el índice; los demás van en FilterExpression (spec-incidencias.md 2.3)
        [$indice, $particion, $valorParticion] = match (true) {
            $filtro->idParcela !== null => ['gsi_parcela', 'id_parcela', $filtro->idParcela],
            $filtro->idCampania !== null => ['gsi_campania', 'id_campania', $filtro->idCampania],
            default => ['gsi_registrador', 'id_registrador', (string) $filtro->idRegistrador],
        };

        $nombres = ['#p' => $particion];
        $valores = [':p' => ['S' => $valorParticion]];
        $condicionClave = '#p = :p';
        if ($filtro->fechaDesde !== null || $filtro->fechaHasta !== null) {
            $nombres['#f'] = 'fecha_observacion';
            $valores[':desde'] = ['S' => $filtro->fechaDesde ?? '0000-00-00'];
            $valores[':hasta'] = ['S' => ($filtro->fechaHasta ?? '9999-12-31').'T99'];
            $condicionClave .= ' AND #f BETWEEN :desde AND :hasta';
        }

        $filtros = [];
        $secundarios = [
            'id_parcela' => $filtro->idParcela,
            'id_campania' => $filtro->idCampania,
            'id_registrador' => $filtro->idRegistrador,
            'tipo' => $filtro->tipo?->value,
        ];
        foreach ($secundarios as $atributo => $valor) {
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
                $filtro->cursor, ['id', $particion, 'fecha_observacion'], [$particion => $valorParticion],
            );
        }

        $resultado = $this->cliente->query($parametros);

        return new Pagina(
            array_map(fn (array $item) => IncidenciaMapper::aIncidencia($this->marshaler->unmarshalItem($item)), $resultado['Items'] ?? []),
            CodificadorCursor::codificar($resultado['LastEvaluatedKey'] ?? null),
        );
    }

    private function tabla(): string
    {
        return $this->tablas->de('incidencias');
    }
}
