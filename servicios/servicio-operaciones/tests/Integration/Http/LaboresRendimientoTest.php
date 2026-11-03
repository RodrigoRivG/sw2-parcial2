<?php

use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\Responsable;
use App\Domain\FieldTask\TipoLabor;
use App\Domain\FieldTask\ValidacionCampania;
use App\Infrastructure\Persistence\DynamoDb\Mappers\LaborMapper;
use App\Infrastructure\Persistence\DynamoDb\NombresTablas;
use Aws\DynamoDb\DynamoDbClient;
use Aws\DynamoDb\Marshaler;
use Tests\Support\DatosLabor;

it('lista y consulta en menos de 3 s con 1.000 labores cargadas (CE-LAB-04)', function () {
    $campania = DatosLabor::uuid();
    $cliente = app(DynamoDbClient::class);
    $marshaler = new Marshaler;
    $base = new DateTimeImmutable('2026-10-01T08:00:00Z', new DateTimeZone('UTC'));
    $ids = [];

    // Carga directa por lotes de 25 (límite de BatchWriteItem): lo que se mide es la lectura
    foreach (array_chunk(range(0, 999), 25) as $lote) {
        $pedidos = [];
        foreach ($lote as $i) {
            $id = DatosLabor::uuid();
            $ids[] = $id;
            $fecha = $base->modify("+{$i} minutes");
            $labor = LaborAgricola::registrarRealizada($id, 'h', TipoLabor::RIEGO, 'p1', $campania, $fecha, $fecha, null, [],
                new Responsable('tec-'.($i % 10), 'Técnico'), ValidacionCampania::VALIDADA, $fecha);
            $pedidos[] = ['PutRequest' => ['Item' => $marshaler->marshalItem(LaborMapper::aItem($labor))]];
        }
        $cliente->batchWriteItem(['RequestItems' => [app(NombresTablas::class)->de('labores') => $pedidos]]);
    }
    $gerente = $this->encabezados(['gerencia']);

    $inicio = microtime(true);
    $pagina = $this->getJson("/api/operaciones/v1/labores?idCampania={$campania}&limite=100", $gerente)->assertOk();
    $listado = microtime(true) - $inicio;

    $inicio = microtime(true);
    $this->getJson("/api/operaciones/v1/labores/{$ids[500]}", $gerente)->assertOk();
    $detalle = microtime(true) - $inicio;

    expect($pagina->json('items'))->toHaveCount(100)
        ->and($pagina->json('items.0.fechaReferencia'))->toBe('2026-10-02T00:39:00Z')
        ->and($listado)->toBeLessThan(3.0)
        ->and($detalle)->toBeLessThan(3.0);
});
