<?php

use Tests\Support\DatosLabor;
use Tests\Support\FlujoSaga;

beforeEach(function () {
    $this->flujo = FlujoSaga::preparar($this)->registrar('1');
});

it('devuelve la Saga con el detalle de cada paso a administrador, gerencia y lectura_operaciones (Historia 7)', function (string $rol) {
    $this->flujo->descontado('4.85');

    $this->getJson("/api/operaciones/v1/sagas/{$this->flujo->idSaga}", $this->encabezados([$rol]))
        ->assertOk()
        ->assertJson([
            'idSaga' => $this->flujo->idSaga,
            'idLabor' => $this->flujo->idLabor,
            'estado' => 'EN_CURSO',
            'pasoActual' => 'REGISTRAR_COSTO',
            'costoTotal' => '4.85',
            'items' => [['cantidad' => '1.000']],
            'pasos' => [
                ['paso' => 'DESCONTAR_INSUMOS', 'estado' => 'COMPLETADO', 'intentos' => 1, 'respuesta' => ['tipo' => 'InsumosDescontados'], 'error' => null],
                ['paso' => 'REGISTRAR_COSTO', 'estado' => 'ENVIADO', 'intentos' => 1, 'fechaRespuesta' => null],
            ],
            'respuestasTardias' => [],
            'version' => 1,
        ])
        ->assertJsonStructure(['fechaLimite', 'fechaCreacion', 'fechaActualizacion', 'pasos' => [['fechaPrimerEnvio', 'fechaUltimoEnvio']]]);
})->with(['administrador', 'gerencia', 'lectura_operaciones']);

it('un técnico de campo no ve las Sagas', function () {
    $this->getJson("/api/operaciones/v1/sagas/{$this->flujo->idSaga}", $this->encabezados(['tecnico_campo']))
        ->assertForbidden()->assertJson(['codigo' => 'SIN_PERMISO']);
});

it('una Saga inexistente es 404 SAGA_NO_ENCONTRADA', function () {
    $this->getJson('/api/operaciones/v1/sagas/'.DatosLabor::uuid(), $this->encabezados(['administrador']))
        ->assertNotFound()->assertJson(['codigo' => 'SAGA_NO_ENCONTRADA']);
});
