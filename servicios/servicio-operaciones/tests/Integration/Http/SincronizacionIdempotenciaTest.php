<?php

use Tests\Support\DatosIncidencia;
use Tests\Support\DatosLabor;
use Tests\Support\GestionFalsa;

beforeEach(function () {
    GestionFalsa::instalar();
    $this->parcela = DatosLabor::uuid();
    $this->campania = DatosLabor::uuid();
    GestionFalsa::campania($this->campania, $this->parcela);
    $this->tecnico = $this->encabezados(['tecnico_campo'], 'tec-ana');
});

/** @param list<mixed> $operaciones */
function lote(array $operaciones, array $fotos = []): array
{
    $partes = ['operaciones' => json_encode($operaciones)];
    foreach ($fotos as $id => $contenido) {
        $partes['fotos'][$id] = DatosIncidencia::archivo($contenido);
    }

    return test()->post('/api/operaciones/v1/sincronizacion', $partes, test()->tecnico)->assertOk()->json();
}

it('reenviar el lote completo devuelve todo SINCRONIZADA repetida, sin efectos nuevos (escenario 1, CE-SIN-02)', function () {
    $labor = DatosLabor::realizada($this->parcela, $this->campania, ['insumos' => DatosLabor::insumos('2'), 'fechaCreacion' => DatosLabor::fecha('-2 minutes')]);
    $incidencia = DatosIncidencia::datos($this->parcela, ['fechaCreacion' => DatosLabor::fecha('-1 minute')]);
    $foto = DatosIncidencia::jpeg();
    $operaciones = [['tipo' => 'REGISTRAR_LABOR', 'datos' => $labor], ['tipo' => 'REGISTRAR_INCIDENCIA', 'datos' => $incidencia]];

    $primero = lote($operaciones, [$incidencia['idOperacion'] => $foto]);
    $version = $this->getJson("/api/operaciones/v1/labores/{$labor['idOperacion']}", $this->encabezados(['gerencia']))->json('version');
    $segundo = lote($operaciones, [$incidencia['idOperacion'] => $foto]);
    $tercero = lote($operaciones, [$incidencia['idOperacion'] => $foto]);

    expect(array_column($primero['resultados'], 'repetida'))->toBe([false, false])
        ->and(array_column($segundo['resultados'], 'repetida'))->toBe([true, true])
        ->and(array_column($tercero['resultados'], 'idRecurso'))->toBe(array_column($primero['resultados'], 'idRecurso'))
        ->and($this->getJson("/api/operaciones/v1/labores/{$labor['idOperacion']}", $this->encabezados(['gerencia']))->json('version'))->toBe($version)
        ->and(DatosIncidencia::objetosDe($incidencia['idOperacion']))->toHaveCount(1)
        ->and(DatosIncidencia::auditorias($incidencia['idOperacion']))->toBe(['REGISTRAR_INCIDENCIA']);
});

it('el mismo idOperacion con otro contenido da ERROR CONFLICTO_IDEMPOTENCIA no reintentable (escenario 2)', function () {
    $labor = DatosLabor::realizada($this->parcela, $this->campania);
    lote([['tipo' => 'REGISTRAR_LABOR', 'datos' => $labor]]);

    $respuesta = lote([['tipo' => 'REGISTRAR_LABOR', 'datos' => [...$labor, 'tipoLabor' => 'COSECHA']]]);

    expect($respuesta['resultados'][0])->toMatchArray(['resultado' => 'ERROR', 'codigo' => 'CONFLICTO_IDEMPOTENCIA', 'reintentable' => false]);
});

it('el mismo idOperacion dos veces en un lote: la segunda vuelve como repetida (escenario 3)', function () {
    $labor = DatosLabor::realizada($this->parcela, $this->campania);

    $respuesta = lote([['tipo' => 'REGISTRAR_LABOR', 'datos' => $labor], ['tipo' => 'REGISTRAR_LABOR', 'datos' => $labor]]);

    expect(array_column($respuesta['resultados'], 'resultado'))->toBe(['SINCRONIZADA', 'SINCRONIZADA'])
        ->and(array_column($respuesta['resultados'], 'repetida'))->toBe([false, true]);
});
