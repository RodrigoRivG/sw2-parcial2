<?php

use App\Application\Contracts\Reloj;
use App\Infrastructure\Messaging\TopologiaSaga;
use Tests\Support\DatosLabor;
use Tests\Support\FlujoSaga;
use Tests\Support\GestionFalsa;
use Tests\Support\RabbitPruebas;
use Tests\Support\RelojFijo;

beforeEach(function () {
    $this->flujo = FlujoSaga::preparar($this);
});

it('confirma la labor: DescontarInsumos → InsumosDescontados → RegistrarCostoCampania → CostoCampaniaRegistrado (Historia 1)', function () {
    $flujo = $this->flujo->registrar('100', '2.5');

    // Escenario 1: Saga guardada y DescontarInsumos con el contrato de inventario (RQ-SAG-09 de inventario)
    expect($flujo->descontar)->toMatchArray([
        'idCorrelacion' => $flujo->idSaga,
        'tipo' => 'DescontarInsumos',
        'version' => 1,
        'origen' => 'servicio-operaciones',
    ])
        ->and($flujo->descontar['idMensaje'])->toMatch('/^[0-9a-f-]{36}$/')
        ->and($flujo->descontar['datos']['idSaga'])->toBe($flujo->idSaga)
        ->and($flujo->descontar['datos']['idLabor'])->toBe($flujo->idLabor)
        ->and(array_column($flujo->descontar['datos']['items'], 'cantidad'))->toBe(['100.000', '2.500'])
        ->and($flujo->labor())->toMatchArray(['estado' => 'PENDIENTE', 'idSaga' => $flujo->idSaga])
        ->and($flujo->saga())->toMatchArray(['estado' => 'EN_CURSO', 'pasoActual' => 'DESCONTAR_INSUMOS']);

    // Escenario 2: el costo de inventario se reenvía tal cual a gestión (2.3 de gestión)
    $flujo->descontado('580.50');
    $registrar = $flujo->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
    expect($registrar['datos'])->toBe([
        'idSaga' => $flujo->idSaga,
        'idLabor' => $flujo->idLabor,
        'idCampania' => $flujo->campania,
        'monto' => '580.50',
        'categoria' => 'INSUMO',
    ]);

    // Escenario 3
    $flujo->responder('CostoCampaniaRegistrado', ['idCampania' => $flujo->campania, 'idCosto' => DatosLabor::uuid(), 'monto' => '580.50']);
    $saga = $flujo->saga();

    expect($flujo->labor())->toMatchArray(['estado' => 'CONFIRMADA', 'motivo' => null])
        ->and($saga)->toMatchArray(['estado' => 'COMPLETADA', 'costoTotal' => '580.50', 'fechaLimite' => null])
        ->and(array_column($saga['pasos'], 'estado', 'paso'))->toBe(['DESCONTAR_INSUMOS' => 'COMPLETADO', 'REGISTRAR_COSTO' => 'COMPLETADO'])
        ->and(FlujoSaga::auditorias('SAGA', $flujo->idSaga))->toEqualCanonicalizing(['INICIAR_SAGA', 'AVANZAR_SAGA', 'AVANZAR_SAGA'])
        ->and(FlujoSaga::auditorias('LABOR', $flujo->idLabor))->toEqualCanonicalizing(['REGISTRAR_LABOR', 'ACTUALIZAR_LABOR_SAGA']);
    $flujo->sinComandos();
});

it('con costo total 0.00 no envía nada a gestión y confirma la labor (escenario 4)', function () {
    $flujo = $this->flujo->registrar('3');

    $flujo->descontado('0.00');

    expect($flujo->labor()['estado'])->toBe('CONFIRMADA')
        ->and($flujo->saga())->toMatchArray(['estado' => 'COMPLETADA', 'costoTotal' => '0.00'])
        ->and(array_column($flujo->saga()['pasos'], 'estado', 'paso'))->toBe(['DESCONTAR_INSUMOS' => 'COMPLETADO', 'REGISTRAR_COSTO' => 'OMITIDO']);
    $flujo->sinComandos();
});

it('inicia la Saga cuando una labor con validación diferida pasa a válida (escenario 5)', function () {
    $flujo = $this->flujo;
    GestionFalsa::disponible(false);
    $cuerpo = DatosLabor::realizada($flujo->parcela, $flujo->campania, ['insumos' => DatosLabor::insumos('7')]);
    $this->postJson('/api/operaciones/v1/labores', $cuerpo, $flujo->tecnico())->assertCreated()->assertJson(['idSaga' => null]);
    $flujo->sinComandos();
    GestionFalsa::disponible(true);

    app()->instance(Reloj::class, new RelojFijo(DatosLabor::fecha('+2 minutes')));
    $this->artisan('labores:revalidar-campanias')->assertSuccessful();

    $descontar = RabbitPruebas::leer(TopologiaSaga::COLA_INVENTARIO);
    $labor = $this->getJson("/api/operaciones/v1/labores/{$cuerpo['idOperacion']}", $this->encabezados(['gerencia']))->json();
    expect($descontar['tipo'] ?? null)->toBe('DescontarInsumos')
        ->and($descontar['idCorrelacion'])->toBe($labor['idSaga'])
        ->and($labor['estado'])->toBe('PENDIENTE');
});

it('también inicia la Saga al realizar una labor programada con insumos', function () {
    $flujo = $this->flujo;
    $programada = DatosLabor::programada($flujo->parcela, $flujo->campania);
    $this->postJson('/api/operaciones/v1/labores', $programada, $this->encabezados(['administrador']))->assertCreated();

    $respuesta = $this->postJson("/api/operaciones/v1/labores/{$programada['idOperacion']}/realizacion",
        DatosLabor::realizacion(['insumos' => DatosLabor::insumos('4')]), $flujo->tecnico())->assertOk();

    $descontar = RabbitPruebas::leer(TopologiaSaga::COLA_INVENTARIO);
    expect($respuesta->json('idSaga'))->toBeString()
        ->and($descontar['idCorrelacion'])->toBe($respuesta->json('idSaga'));
});
