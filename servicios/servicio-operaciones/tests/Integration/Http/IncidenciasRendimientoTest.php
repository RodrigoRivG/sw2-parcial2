<?php

use App\Domain\FieldTask\Responsable;
use App\Domain\Incident\Incidencia;
use App\Domain\Incident\ReferenciaFoto;
use App\Domain\Incident\TipoIncidencia;
use App\Infrastructure\Persistence\DynamoDb\Mappers\IncidenciaMapper;
use App\Infrastructure\Persistence\DynamoDb\NombresTablas;
use Aws\DynamoDb\DynamoDbClient;
use Aws\DynamoDb\Marshaler;
use Tests\Support\DatosIncidencia;
use Tests\Support\DatosLabor;

it('registra una foto de 5 MB y lista 100 incidencias con sus URL en menos de 3 s (CE-INC-04)', function () {
    $parcela = DatosLabor::uuid();

    $inicio = microtime(true);
    DatosIncidencia::enviar($this, DatosIncidencia::datos($parcela), DatosIncidencia::jpeg(5 * 1024 * 1024), $this->encabezados(['tecnico_campo']))->assertCreated();
    $registro = microtime(true) - $inicio;

    // 100 incidencias cargadas directo en DynamoDB: lo que se mide es la lectura con la firma de las URL
    $ahora = new DateTimeImmutable('now', new DateTimeZone('UTC'));
    $marshaler = new Marshaler;
    foreach (array_chunk(range(1, 100), 25) as $lote) {
        $pedidos = [];
        foreach ($lote as $i) {
            $id = DatosLabor::uuid();
            $incidencia = Incidencia::registrar($id, 'h', TipoIncidencia::OTRO, "Incidencia {$i}", $ahora->modify("-{$i} minutes"), $ahora, $parcela, null,
                new ReferenciaFoto("incidencias/{$id}/x.jpg", 'image/jpeg', 10), null, new Responsable('tec', 'Ana'), $ahora);
            $pedidos[] = ['PutRequest' => ['Item' => $marshaler->marshalItem(IncidenciaMapper::aItem($incidencia))]];
        }
        app(DynamoDbClient::class)->batchWriteItem(['RequestItems' => [app(NombresTablas::class)->de('incidencias') => $pedidos]]);
    }

    $inicio = microtime(true);
    $pagina = $this->getJson("/api/operaciones/v1/incidencias?idParcela={$parcela}&limite=100", $this->encabezados(['gerencia']))->assertOk();
    $listado = microtime(true) - $inicio;

    expect($pagina->json('items'))->toHaveCount(100)
        ->and($registro)->toBeLessThan(3.0)
        ->and($listado)->toBeLessThan(3.0);
});
