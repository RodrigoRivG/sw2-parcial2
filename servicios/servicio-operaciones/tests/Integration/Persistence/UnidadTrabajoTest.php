<?php

use App\Application\Contracts\ConflictoEscritura;
use App\Application\Contracts\RegistroAuditoria;
use App\Application\Contracts\UnidadTrabajo;
use App\Infrastructure\Persistence\DynamoDb\NombresTablas;
use App\Infrastructure\Persistence\DynamoDb\UnidadTrabajoDynamo;
use Aws\DynamoDb\DynamoDbClient;
use Aws\DynamoDb\Marshaler;
use Illuminate\Support\Facades\Context;
use Illuminate\Support\Str;

function ponerItem(string $id, string $etiqueta): void
{
    app(UnidadTrabajoDynamo::class)->agregar([
        'Put' => [
            'TableName' => app(NombresTablas::class)->de('labores'),
            'Item' => (new Marshaler)->marshalItem(['id' => $id, 'estado' => 'PROGRAMADA', 'fecha_referencia' => '2026-11-02']),
            'ConditionExpression' => 'attribute_not_exists(id)',
        ],
    ], $etiqueta);
}

function existeItem(string $tabla, string $id): bool
{
    $resultado = app(DynamoDbClient::class)->getItem([
        'TableName' => app(NombresTablas::class)->de($tabla),
        'Key' => ['id' => ['S' => $id]],
        'ConsistentRead' => true,
    ]);

    return isset($resultado['Item']);
}

/** @return list<array<string, mixed>> */
function auditoriasDe(string $entidad, string $idEntidad): array
{
    $resultado = app(DynamoDbClient::class)->query([
        'TableName' => app(NombresTablas::class)->de('registros_auditoria'),
        'IndexName' => 'gsi_entidad',
        'KeyConditionExpression' => 'entidad_id = :e',
        'ExpressionAttributeValues' => [':e' => ['S' => "{$entidad}#{$idEntidad}"]],
    ]);

    return array_map(fn ($item) => (new Marshaler)->unmarshalItem($item), $resultado['Items'] ?? []);
}

it('escribe la entidad y su auditoría en una sola transacción, con actor e idCorrelacion', function () {
    Context::add('idCorrelacion', 'correlacion-1');
    $id = (string) Str::uuid();

    app(UnidadTrabajo::class)->ejecutar(function () use ($id) {
        ponerItem($id, 'labor');
        app(RegistroAuditoria::class)->registrar('usuario-1', 'PROGRAMAR_LABOR', 'LABOR', $id);
    });

    expect(existeItem('labores', $id))->toBeTrue();
    $auditorias = auditoriasDe('LABOR', $id);
    expect($auditorias)->toHaveCount(1)
        ->and($auditorias[0])->toMatchArray([
            'actor' => 'usuario-1',
            'accion' => 'PROGRAMAR_LABOR',
            'entidad' => 'LABOR',
            'id_entidad' => $id,
            'id_correlacion' => 'correlacion-1',
        ]);
});

it('no escribe nada si falla una condición e informa qué escritura falló', function () {
    $existente = (string) Str::uuid();
    ponerItem($existente, 'previa');
    $nuevo = (string) Str::uuid();

    $error = null;
    try {
        app(UnidadTrabajo::class)->ejecutar(function () use ($existente, $nuevo) {
            ponerItem($nuevo, 'nueva');
            ponerItem($existente, 'repetida');
            app(RegistroAuditoria::class)->registrar('usuario-1', 'PROGRAMAR_LABOR', 'LABOR', $nuevo);
        });
    } catch (ConflictoEscritura $e) {
        $error = $e;
    }

    expect($error)->not->toBeNull()
        ->and($error->etiqueta)->toBe('repetida')
        ->and(existeItem('labores', $nuevo))->toBeFalse()
        ->and(auditoriasDe('LABOR', $nuevo))->toBe([]);
});

it('anida unidades de trabajo en una sola transacción', function () {
    $id = (string) Str::uuid();
    $unidad = app(UnidadTrabajo::class);

    $unidad->ejecutar(function () use ($unidad, $id) {
        ponerItem($id, 'labor');
        $unidad->ejecutar(fn () => app(RegistroAuditoria::class)->registrar('usuario-1', 'REGISTRAR_LABOR', 'LABOR', $id));
        // Dentro de la transacción todavía no se escribió nada
        expect(existeItem('labores', $id))->toBeFalse();
    });

    expect(existeItem('labores', $id))->toBeTrue()
        ->and(auditoriasDe('LABOR', $id))->toHaveCount(1);
});

it('no escribe nada si la operación lanza una excepción', function () {
    $id = (string) Str::uuid();

    expect(fn () => app(UnidadTrabajo::class)->ejecutar(function () use ($id) {
        ponerItem($id, 'labor');
        throw new RuntimeException('falla de negocio');
    }))->toThrow(RuntimeException::class);

    expect(existeItem('labores', $id))->toBeFalse();
});

it('fuera de una unidad de trabajo, cada escritura se envía sola', function () {
    $id = (string) Str::uuid();
    ponerItem($id, 'suelta');

    expect(existeItem('labores', $id))->toBeTrue()
        ->and(fn () => ponerItem($id, 'suelta'))->toThrow(ConflictoEscritura::class);
});
