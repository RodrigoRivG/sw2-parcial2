<?php

use Illuminate\Testing\TestResponse;
use Tests\Support\DatosIncidencia;
use Tests\Support\DatosLabor;
use Tests\Support\GestionFalsa;

const RUTA_SINCRONIZACION = '/api/operaciones/v1/sincronizacion';

beforeEach(function () {
    GestionFalsa::instalar();
    $this->parcela = DatosLabor::uuid();
    $this->campania = DatosLabor::uuid();
    GestionFalsa::campania($this->campania, $this->parcela);
    $this->tecnico = $this->encabezados(['tecnico_campo'], 'tec-ana');
});

/**
 * @param  list<mixed>  $operaciones
 * @param  array<string, string>  $fotos  idOperacion => contenido
 */
function enviarLote(array $operaciones, array $fotos = [], ?array $encabezados = null, array $extra = []): TestResponse
{
    $partes = ['operaciones' => json_encode($operaciones), ...$extra];
    foreach ($fotos as $id => $contenido) {
        $partes['fotos'][$id] = DatosIncidencia::archivo($contenido);
    }

    return test()->post(RUTA_SINCRONIZACION, $partes, $encabezados ?? test()->tecnico);
}

function labor(array $datos): array
{
    return ['tipo' => 'REGISTRAR_LABOR', 'datos' => $datos];
}

describe('Historia 1 — lote con resultados mixtos', function () {
    it('sincroniza labor realizada, programada e incidencia con foto (escenario 1)', function () {
        $realizada = DatosLabor::realizada($this->parcela, $this->campania, ['fechaCreacion' => DatosLabor::fecha('-3 minutes')]);
        $programada = DatosLabor::programada($this->parcela, $this->campania, ['fechaCreacion' => DatosLabor::fecha('-2 minutes')]);
        $incidencia = DatosIncidencia::datos($this->parcela, ['fechaCreacion' => DatosLabor::fecha('-1 minute')]);

        enviarLote([labor($realizada), labor($programada), ['tipo' => 'REGISTRAR_INCIDENCIA', 'datos' => $incidencia]],
            [$incidencia['idOperacion'] => DatosIncidencia::jpeg()])
            ->assertOk()
            ->assertExactJson([
                'resultados' => [
                    ['idOperacion' => $realizada['idOperacion'], 'tipo' => 'REGISTRAR_LABOR', 'resultado' => 'SINCRONIZADA', 'repetida' => false, 'idRecurso' => $realizada['idOperacion'], 'estado' => 'CONFIRMADA'],
                    ['idOperacion' => $programada['idOperacion'], 'tipo' => 'REGISTRAR_LABOR', 'resultado' => 'SINCRONIZADA', 'repetida' => false, 'idRecurso' => $programada['idOperacion'], 'estado' => 'PROGRAMADA'],
                    ['idOperacion' => $incidencia['idOperacion'], 'tipo' => 'REGISTRAR_INCIDENCIA', 'resultado' => 'SINCRONIZADA', 'repetida' => false, 'idRecurso' => $incidencia['idOperacion'], 'estado' => null],
                ],
                'resumen' => ['sincronizadas' => 3, 'errores' => 0],
            ]);

        $this->getJson("/api/operaciones/v1/incidencias/{$incidencia['idOperacion']}", $this->encabezados(['gerencia']))->assertOk();
        expect(DatosIncidencia::auditorias($incidencia['idOperacion']))->toBe(['REGISTRAR_INCIDENCIA']);
    });

    it('procesa en orden cronológico y, a igual fecha, por idOperacion (escenario 2)', function () {
        $misma = DatosLabor::fecha('-5 minutes');
        $ops = [
            DatosLabor::realizada($this->parcela, $this->campania, ['fechaCreacion' => DatosLabor::fecha('-1 minute')]),
            DatosLabor::realizada($this->parcela, $this->campania, ['fechaCreacion' => $misma, 'idOperacion' => 'bbbbbbbb-0000-4000-8000-000000000000']),
            DatosLabor::realizada($this->parcela, $this->campania, ['fechaCreacion' => DatosLabor::fecha('-9 minutes')]),
            DatosLabor::realizada($this->parcela, $this->campania, ['fechaCreacion' => $misma, 'idOperacion' => 'aaaaaaaa-0000-4000-8000-000000000000']),
        ];

        $respuesta = enviarLote(array_map(fn ($d) => labor($d), $ops))->assertOk();

        expect(array_column($respuesta->json('resultados'), 'idOperacion'))->toBe([
            $ops[2]['idOperacion'], 'aaaaaaaa-0000-4000-8000-000000000000', 'bbbbbbbb-0000-4000-8000-000000000000', $ops[0]['idOperacion'],
        ]);
    });

    it('una labor en campaña finalizada da ERROR y las demás se sincronizan igual (escenario 3)', function () {
        $finalizada = DatosLabor::uuid();
        GestionFalsa::campania($finalizada, $this->parcela, 'FINALIZADA');
        $ops = [
            DatosLabor::realizada($this->parcela, $this->campania, ['fechaCreacion' => DatosLabor::fecha('-3 minutes')]),
            DatosLabor::realizada($this->parcela, $finalizada, ['fechaCreacion' => DatosLabor::fecha('-2 minutes')]),
            DatosLabor::realizada($this->parcela, $this->campania, ['fechaCreacion' => DatosLabor::fecha('-1 minute')]),
        ];

        $respuesta = enviarLote(array_map(fn ($d) => labor($d), $ops))->assertOk();

        expect(array_column($respuesta->json('resultados'), 'resultado'))->toBe(['SINCRONIZADA', 'ERROR', 'SINCRONIZADA'])
            ->and($respuesta->json('resultados.1'))->toMatchArray([
                'codigo' => 'CAMPANIA_FINALIZADA', 'mensaje' => 'No se pueden registrar labores en una campaña finalizada.', 'reintentable' => false,
            ])
            ->and($respuesta->json('resumen'))->toBe(['sincronizadas' => 2, 'errores' => 1]);
    });

    it('programación y realización en el mismo lote: la programación se procesa antes (escenario 4)', function () {
        $programada = DatosLabor::programada($this->parcela, $this->campania, ['fechaCreacion' => DatosLabor::fecha('-10 minutes')]);
        $realizacion = ['tipo' => 'REALIZAR_LABOR', 'datos' => [...DatosLabor::realizacion(['fechaCreacion' => DatosLabor::fecha('-1 minute')]), 'idLabor' => $programada['idOperacion']]];

        $respuesta = enviarLote([$realizacion, labor($programada)])->assertOk();

        expect(array_column($respuesta->json('resultados'), 'estado'))->toBe(['PROGRAMADA', 'CONFIRMADA'])
            ->and($respuesta->json('resultados.1.idRecurso'))->toBe($programada['idOperacion']);
    });

    it('una realización anterior a su programación da LABOR_NO_ENCONTRADA (escenario 5)', function () {
        $programada = DatosLabor::programada($this->parcela, $this->campania, ['fechaCreacion' => DatosLabor::fecha('-1 minute')]);
        $realizacion = ['tipo' => 'REALIZAR_LABOR', 'datos' => [...DatosLabor::realizacion(['fechaCreacion' => DatosLabor::fecha('-10 minutes')]), 'idLabor' => $programada['idOperacion']]];

        $respuesta = enviarLote([labor($programada), $realizacion])->assertOk();

        expect(array_column($respuesta->json('resultados'), 'resultado'))->toBe(['ERROR', 'SINCRONIZADA'])
            ->and($respuesta->json('resultados.0.codigo'))->toBe('LABOR_NO_ENCONTRADA')
            ->and($respuesta->json('resultados.1.estado'))->toBe('PROGRAMADA');
    });

    it('una labor con insumos queda PENDIENTE (escenario 6)', function () {
        $respuesta = enviarLote([labor(DatosLabor::realizada($this->parcela, $this->campania, ['insumos' => DatosLabor::insumos('3')]))])->assertOk();

        expect($respuesta->json('resultados.0.estado'))->toBe('PENDIENTE');
    });
});

describe('Historia 3 — sin perder operaciones', function () {
    it('con gestión caída las labores se sincronizan como PENDIENTE, no como error (escenario 1)', function () {
        GestionFalsa::disponible(false);

        $respuesta = enviarLote([labor(DatosLabor::realizada($this->parcela, $this->campania))])->assertOk();

        expect($respuesta->json('resultados.0'))->toMatchArray(['resultado' => 'SINCRONIZADA', 'estado' => 'PENDIENTE']);
    });

    it('consulta cada campaña una sola vez por lote (escenario 3)', function () {
        $otra = DatosLabor::uuid();
        GestionFalsa::campania($otra, $this->parcela);
        $ops = [];
        foreach (range(1, 6) as $i) {
            $ops[] = labor(DatosLabor::realizada($this->parcela, $i % 2 === 0 ? $this->campania : $otra));
        }

        enviarLote($ops)->assertOk()->assertJson(['resumen' => ['sincronizadas' => 6, 'errores' => 0]]);

        expect(GestionFalsa::consultas())->toBe(2);
    });
});

describe('Historia 4 — lotes mal formados', function () {
    it('rechaza el lote entero con 400 (escenario 1)', function (Closure $partes) {
        $this->post(RUTA_SINCRONIZACION, $partes(), $this->tecnico)->assertStatus(400)->assertJson(['codigo' => 'DATOS_INVALIDOS']);
    })->with([
        'sin operaciones' => fn () => [],
        'no es JSON' => fn () => ['operaciones' => '[{'],
        'no es una lista' => fn () => ['operaciones' => '{"tipo": "REGISTRAR_LABOR"}'],
        'lista vacía' => fn () => ['operaciones' => '[]'],
        '51 operaciones' => fn () => ['operaciones' => json_encode(array_fill(0, 51, ['tipo' => 'REGISTRAR_LABOR', 'datos' => []]))],
        'parte no permitida' => fn () => ['operaciones' => '[{}]', 'otra' => 'x'],
    ]);

    it('una operación sin sobre válido da ERROR DATOS_INVALIDOS al final y el resto se procesa (escenario 2)', function () {
        $valida = DatosLabor::realizada($this->parcela, $this->campania);
        $sinFecha = DatosLabor::realizada($this->parcela, $this->campania);
        unset($sinFecha['fechaCreacion']);
        $tipoDesconocido = DatosLabor::realizada($this->parcela, $this->campania);

        $respuesta = enviarLote([
            ['tipo' => 'BORRAR_LABOR', 'datos' => $tipoDesconocido],
            labor($sinFecha),
            labor($valida),
            'no es un objeto',
            ['tipo' => 'REGISTRAR_LABOR', 'datos' => [...$valida, 'idOperacion' => 'no-uuid']],
        ])->assertOk();

        $resultados = $respuesta->json('resultados');
        expect($resultados[0])->toMatchArray(['idOperacion' => $valida['idOperacion'], 'resultado' => 'SINCRONIZADA'])
            ->and(array_column(array_slice($resultados, 1), 'codigo'))->toBe(['DATOS_INVALIDOS', 'DATOS_INVALIDOS', 'DATOS_INVALIDOS', 'DATOS_INVALIDOS'])
            // El idOperacion se devuelve si se pudo leer, para que la app sepa cuál falló
            ->and(array_column(array_slice($resultados, 1), 'idOperacion'))->toBe([$tipoDesconocido['idOperacion'], $sinFecha['idOperacion'], null, 'no-uuid'])
            ->and($respuesta->json('resumen'))->toBe(['sincronizadas' => 1, 'errores' => 4]);
    });

    it('valida cada operación como su endpoint: 400 en datos y 422 en reglas, sin detener el lote', function () {
        $sinFoto = DatosIncidencia::datos($this->parcela, ['fechaCreacion' => DatosLabor::fecha('-4 minutes')]);
        $fotoMala = DatosIncidencia::datos($this->parcela, ['fechaCreacion' => DatosLabor::fecha('-3 minutes')]);
        $campoExtra = DatosLabor::realizada($this->parcela, $this->campania, ['fechaCreacion' => DatosLabor::fecha('-2 minutes'), 'responsable' => 'Juan']);
        $cantidadCero = DatosLabor::realizada($this->parcela, $this->campania, ['fechaCreacion' => DatosLabor::fecha('-1 minute'), 'insumos' => DatosLabor::insumos('0')]);

        $respuesta = enviarLote([
            ['tipo' => 'REGISTRAR_INCIDENCIA', 'datos' => $sinFoto],
            ['tipo' => 'REGISTRAR_INCIDENCIA', 'datos' => $fotoMala],
            labor($campoExtra),
            labor($cantidadCero),
        ], [$fotoMala['idOperacion'] => 'GIF89a'])->assertOk();

        $resultados = $respuesta->json('resultados');
        expect(array_column($resultados, 'codigo'))->toBe(['DATOS_INVALIDOS', 'FOTO_INVALIDA', 'DATOS_INVALIDOS', 'CANTIDAD_INVALIDA'])
            ->and($resultados[0]['detalles'][0]['campo'])->toBe("fotos[{$sinFoto['idOperacion']}]")
            ->and($resultados[2]['detalles'][0])->toMatchArray(['campo' => 'responsable']);
    });

    it('recorta los textos como en una solicitud normal', function () {
        $datos = DatosLabor::realizada($this->parcela, $this->campania, ['observaciones' => '   ', 'insumos' => [['idInsumo' => DatosLabor::uuid(), 'cantidad' => ' 2.5 ']]]);

        $respuesta = enviarLote([labor($datos)])->assertOk()->assertJson(['resultados' => [['resultado' => 'SINCRONIZADA']]]);

        $this->getJson("/api/operaciones/v1/labores/{$datos['idOperacion']}", $this->encabezados(['gerencia']))
            ->assertJson(['observaciones' => null, 'insumos' => [['cantidad' => '2.500']]]);
        expect($respuesta->json('resultados.0.estado'))->toBe('PENDIENTE');
    });

    it('exige tecnico_campo y token (escenario 4)', function () {
        enviarLote([labor(DatosLabor::realizada($this->parcela, $this->campania))], encabezados: $this->encabezados(['administrador']))
            ->assertForbidden()->assertJson(['codigo' => 'SIN_PERMISO']);
        $this->post(RUTA_SINCRONIZACION, ['operaciones' => '[]'], ['Accept' => 'application/json'])->assertUnauthorized();
    });
});
