<?php

use Tests\Support\DatosLabor;
use Tests\Support\GestionFalsa;

/**
 * @return array{0: float, 1: array<string, mixed>} segundos y respuesta
 */
function loteDe50(string $parcela, array $campanias): array
{
    $operaciones = [];
    foreach (range(0, 49) as $i) {
        $operaciones[] = ['tipo' => 'REGISTRAR_LABOR', 'datos' => DatosLabor::realizada($parcela, $campanias[$i % 5], [
            'fechaCreacion' => DatosLabor::fecha('-'.(60 - $i).' seconds'),
        ])];
    }
    $inicio = microtime(true);
    $respuesta = test()->post('/api/operaciones/v1/sincronizacion', ['operaciones' => json_encode($operaciones)], test()->encabezados(['tecnico_campo']))
        ->assertOk()->json();

    return [microtime(true) - $inicio, $respuesta];
}

beforeEach(function () {
    GestionFalsa::instalar();
    $this->parcela = DatosLabor::uuid();
    $this->campanias = array_map(fn () => DatosLabor::uuid(), range(1, 5));
    foreach ($this->campanias as $campania) {
        GestionFalsa::campania($campania, $this->parcela);
    }
});

it('50 labores de 5 campañas en menos de 5 s con gestión respondiendo en 50 ms (CE-SIN-03)', function () {
    GestionFalsa::demora(50);

    [$segundos, $respuesta] = loteDe50($this->parcela, $this->campanias);

    expect($respuesta['resumen'])->toBe(['sincronizadas' => 50, 'errores' => 0])
        ->and(GestionFalsa::consultas())->toBe(5)
        ->and($segundos)->toBeLessThan(5.0);
});

it('con gestión caída (2 s de tiempo límite por consulta) el lote termina en menos de 15 s, todas PENDIENTE (CE-SIN-03)', function () {
    GestionFalsa::demora(2000);
    GestionFalsa::disponible(false);

    [$segundos, $respuesta] = loteDe50($this->parcela, $this->campanias);

    expect(array_count_values(array_column($respuesta['resultados'], 'estado')))->toBe(['PENDIENTE' => 50])
        ->and(GestionFalsa::consultas())->toBe(5)
        ->and($segundos)->toBeLessThan(15.0);
});
