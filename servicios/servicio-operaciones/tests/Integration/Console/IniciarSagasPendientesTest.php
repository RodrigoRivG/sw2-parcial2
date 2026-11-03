<?php

use App\Application\Contracts\UnidadTrabajo;
use App\Domain\FieldTask\ConsumoInsumo;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\RepositorioLabor;
use App\Domain\FieldTask\Responsable;
use App\Domain\FieldTask\TipoLabor;
use App\Domain\FieldTask\ValidacionCampania;
use App\Domain\Shared\Cantidad;
use App\Infrastructure\Messaging\TopologiaSaga;
use Tests\Support\DatosLabor;
use Tests\Support\FlujoSaga;
use Tests\Support\RabbitPruebas;

/** Guarda una labor como la dejaba spec-labores.md antes de existir la Saga (RQ-LAB-08). */
function laborAnteriorALaSaga(ValidacionCampania $validacion): string
{
    $ahora = new DateTimeImmutable('now', new DateTimeZone('UTC'));
    $labor = LaborAgricola::registrarRealizada(DatosLabor::uuid(), 'h', TipoLabor::FERTILIZACION, DatosLabor::uuid(), DatosLabor::uuid(),
        $ahora, $ahora, null, [new ConsumoInsumo(DatosLabor::uuid(), Cantidad::desdeTexto('8'))], new Responsable('tec', 'Ana'), $validacion, $ahora);
    app(UnidadTrabajo::class)->ejecutar(fn () => app(RepositorioLabor::class)->guardarNueva($labor));

    return $labor->id;
}

beforeEach(function () {
    FlujoSaga::preparar($this);
});

it('inicia la Saga de las labores PENDIENTE con insumos y campaña validada que no la tenían, una sola vez', function () {
    $sinSaga = laborAnteriorALaSaga(ValidacionCampania::VALIDADA);
    $conValidacionDiferida = laborAnteriorALaSaga(ValidacionCampania::PENDIENTE);

    $this->artisan('sagas:iniciar-pendientes')->assertSuccessful();
    $this->artisan('sagas:iniciar-pendientes')->assertSuccessful();

    $comandos = RabbitPruebas::leerTodos(TopologiaSaga::COLA_INVENTARIO);
    $labor = app(RepositorioLabor::class)->buscar($sinSaga);
    expect($comandos)->toHaveCount(1)
        ->and($comandos[0]['tipo'])->toBe('DescontarInsumos')
        ->and($comandos[0]['datos']['idLabor'])->toBe($sinSaga)
        ->and($labor->idSaga)->toBe($comandos[0]['idCorrelacion'])
        ->and($labor->version)->toBe(1)
        ->and(app(RepositorioLabor::class)->buscar($conValidacionDiferida)->idSaga)->toBeNull()
        ->and(FlujoSaga::auditorias('SAGA', $labor->idSaga))->toBe(['INICIAR_SAGA']);
});
