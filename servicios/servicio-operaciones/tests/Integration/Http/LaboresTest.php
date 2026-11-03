<?php

use App\Infrastructure\Persistence\DynamoDb\NombresTablas;
use Aws\DynamoDb\DynamoDbClient;
use Tests\Support\DatosLabor;
use Tests\Support\GestionFalsa;

const RUTA_LABORES = '/api/operaciones/v1/labores';

beforeEach(function () {
    GestionFalsa::instalar();
    $this->parcela = DatosLabor::uuid();
    $this->campania = DatosLabor::uuid();
    GestionFalsa::campania($this->campania, $this->parcela);
    $this->tecnico = $this->encabezados(['tecnico_campo'], 'tec-ana');
    $this->admin = $this->encabezados(['administrador'], 'adm-luis');
    $this->gerente = $this->encabezados(['gerencia'], 'ger-1');
});

function accionesAuditadas(string $idLabor): array
{
    $resultado = app(DynamoDbClient::class)->query([
        'TableName' => app(NombresTablas::class)->de('registros_auditoria'),
        'IndexName' => 'gsi_entidad',
        'KeyConditionExpression' => 'entidad_id = :e',
        'ExpressionAttributeValues' => [':e' => ['S' => "LABOR#{$idLabor}"]],
    ]);

    return array_map(fn ($item) => $item['accion']['S'], $resultado['Items']);
}

describe('Historia 1 — registrar una labor realizada', function () {
    it('sin insumos queda CONFIRMADA, con Location, responsable del token y auditoría', function () {
        $cuerpo = DatosLabor::realizada($this->parcela, $this->campania, ['observaciones' => '  Riego de la mañana ']);

        $respuesta = $this->postJson(RUTA_LABORES, $cuerpo, $this->tecnico)
            ->assertCreated()
            ->assertHeader('Location', url(RUTA_LABORES.'/'.$cuerpo['idOperacion']))
            ->assertJson([
                'id' => $cuerpo['idOperacion'],
                'estado' => 'CONFIRMADA',
                'validacionCampania' => 'VALIDADA',
                'responsable' => ['id' => 'tec-ana', 'nombre' => 'Usuario tec-ana'],
                'programadaPor' => null,
                'observaciones' => 'Riego de la mañana',
                'insumos' => [],
                'idSaga' => null,
                'motivo' => null,
                'fechaEjecucion' => $cuerpo['fechaEjecucion'],
                'fechaReferencia' => $cuerpo['fechaEjecucion'],
                'version' => 0,
            ]);

        expect($respuesta->json('fechaRecepcion'))->toMatch('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/')
            ->and(accionesAuditadas($cuerpo['idOperacion']))->toBe(['REGISTRAR_LABOR']);
    });

    it('con insumos queda PENDIENTE con las cantidades en escala 3', function () {
        $insumos = [['idInsumo' => DatosLabor::uuid(), 'cantidad' => '100'], ['idInsumo' => DatosLabor::uuid(), 'cantidad' => '2.5']];

        $this->postJson(RUTA_LABORES, DatosLabor::realizada($this->parcela, $this->campania, ['insumos' => $insumos]), $this->tecnico)
            ->assertCreated()
            ->assertJson(['estado' => 'PENDIENTE', 'insumos' => [
                ['idInsumo' => $insumos[0]['idInsumo'], 'cantidad' => '100.000'],
                ['idInsumo' => $insumos[1]['idInsumo'], 'cantidad' => '2.500'],
            ]]);
    });

    it('acepta una campaña PLANIFICADA', function () {
        GestionFalsa::campania($this->campania, $this->parcela, 'PLANIFICADA');

        $this->postJson(RUTA_LABORES, DatosLabor::realizada($this->parcela, $this->campania), $this->tecnico)
            ->assertCreated()->assertJson(['estado' => 'CONFIRMADA']);
    });

    it('rechaza la campaña finalizada, inexistente o de otra parcela sin guardar nada', function (Closure $preparar, int $estado, string $codigo) {
        $cuerpo = $preparar($this->parcela, $this->campania);

        $this->postJson(RUTA_LABORES, $cuerpo, $this->tecnico)->assertStatus($estado)->assertJson(['codigo' => $codigo]);
        $this->getJson(RUTA_LABORES.'/'.$cuerpo['idOperacion'], $this->admin)->assertNotFound();
    })->with([
        'finalizada' => [function ($parcela, $campania) {
            GestionFalsa::campania($campania, $parcela, 'FINALIZADA');

            return DatosLabor::realizada($parcela, $campania);
        }, 422, 'CAMPANIA_FINALIZADA'],
        'inexistente' => [fn ($parcela) => DatosLabor::realizada($parcela, DatosLabor::uuid()), 404, 'CAMPANIA_NO_ENCONTRADA'],
        'otra parcela' => [fn ($parcela, $campania) => DatosLabor::realizada(DatosLabor::uuid(), $campania), 422, 'PARCELA_NO_CORRESPONDE'],
    ]);

    it('rechaza una ejecución en el futuro con 422', function () {
        $this->postJson(RUTA_LABORES, DatosLabor::realizada($this->parcela, $this->campania, ['fechaEjecucion' => DatosLabor::fecha('+10 minutes')]), $this->tecnico)
            ->assertStatus(422)->assertJson(['codigo' => 'FECHA_EJECUCION_INVALIDA']);
    });

    it('cantidad 0 o negativa es 422 CANTIDAD_INVALIDA', function (string $cantidad) {
        $this->postJson(RUTA_LABORES, DatosLabor::realizada($this->parcela, $this->campania, ['insumos' => DatosLabor::insumos($cantidad)]), $this->tecnico)
            ->assertStatus(422)->assertJson(['codigo' => 'CANTIDAD_INVALIDA']);
    })->with(['0', '-1']);

    it('responde 400 DATOS_INVALIDOS ante formato inválido', function (Closure $cambiar) {
        $cuerpo = $cambiar(DatosLabor::realizada($this->parcela, $this->campania));

        $this->postJson(RUTA_LABORES, $cuerpo, $this->tecnico)->assertStatus(400)->assertJson(['codigo' => 'DATOS_INVALIDOS']);
    })->with([
        'cantidad como número JSON' => fn (array $c) => [...$c, 'insumos' => [['idInsumo' => DatosLabor::uuid(), 'cantidad' => 2.5]]],
        'más de 3 decimales' => fn (array $c) => [...$c, 'insumos' => DatosLabor::insumos('1.2345')],
        'insumo repetido' => function (array $c) {
            $id = DatosLabor::uuid();

            return [...$c, 'insumos' => [['idInsumo' => $id, 'cantidad' => '1'], ['idInsumo' => strtoupper($id), 'cantidad' => '2']]];
        },
        'más de 20 insumos' => fn (array $c) => [...$c, 'insumos' => DatosLabor::insumos(...array_fill(0, 21, '1'))],
        'idOperacion que no es UUID' => fn (array $c) => [...$c, 'idOperacion' => 'abc'],
        'campo no permitido' => fn (array $c) => [...$c, 'responsable' => 'Juan'],
        'tipo de labor desconocido' => fn (array $c) => [...$c, 'tipoLabor' => 'PODA'],
        'ambas fechas' => fn (array $c) => [...$c, 'fechaProgramada' => '2026-12-01'],
        'ninguna fecha' => function (array $c) {
            unset($c['fechaEjecucion']);

            return $c;
        },
        'fecha con zona horaria' => fn (array $c) => [...$c, 'fechaEjecucion' => '2026-11-02T10:00:00-04:00'],
    ]);

    it('un administrador o gerente sin tecnico_campo no registra labores realizadas', function (string $rol) {
        $this->postJson(RUTA_LABORES, DatosLabor::realizada($this->parcela, $this->campania), $this->encabezados([$rol]))
            ->assertForbidden()->assertJson(['codigo' => 'SIN_PERMISO']);
    })->with(['administrador', 'gerencia']);
});

describe('Historia 2 — programar y realizar', function () {
    it('un administrador programa una labor sin efectos', function () {
        $cuerpo = DatosLabor::programada($this->parcela, $this->campania);

        $this->postJson(RUTA_LABORES, $cuerpo, $this->admin)
            ->assertCreated()
            ->assertJson([
                'estado' => 'PROGRAMADA',
                'fechaProgramada' => $cuerpo['fechaProgramada'],
                'fechaReferencia' => $cuerpo['fechaProgramada'],
                'fechaEjecucion' => null,
                'responsable' => ['id' => 'adm-luis'],
                'programadaPor' => ['id' => 'adm-luis'],
            ]);
        expect(accionesAuditadas($cuerpo['idOperacion']))->toBe(['PROGRAMAR_LABOR']);
    });

    it('rechaza una fecha programada anterior a la creación', function () {
        $this->postJson(RUTA_LABORES, DatosLabor::programada($this->parcela, $this->campania, ['fechaProgramada' => '2020-01-01']), $this->admin)
            ->assertStatus(422)->assertJson(['codigo' => 'FECHA_PROGRAMADA_INVALIDA']);
    });

    it('una programada no admite insumos', function () {
        $this->postJson(RUTA_LABORES, DatosLabor::programada($this->parcela, $this->campania, ['insumos' => DatosLabor::insumos('1')]), $this->admin)
            ->assertStatus(400);
    });

    it('un técnico la realiza con insumos: PENDIENTE, nuevo responsable y programadaPor conservado', function () {
        $programada = DatosLabor::programada($this->parcela, $this->campania);
        $this->postJson(RUTA_LABORES, $programada, $this->admin)->assertCreated();
        $realizacion = DatosLabor::realizacion(['insumos' => DatosLabor::insumos('50')]);

        $this->postJson(RUTA_LABORES."/{$programada['idOperacion']}/realizacion", $realizacion, $this->tecnico)
            ->assertOk()
            ->assertJson([
                'estado' => 'PENDIENTE',
                'responsable' => ['id' => 'tec-ana'],
                'programadaPor' => ['id' => 'adm-luis'],
                'fechaProgramada' => $programada['fechaProgramada'],
                'fechaEjecucion' => $realizacion['fechaEjecucion'],
                'fechaReferencia' => $realizacion['fechaEjecucion'],
                'version' => 1,
            ]);
        expect(accionesAuditadas($programada['idOperacion']))->toEqualCanonicalizing(['PROGRAMAR_LABOR', 'REALIZAR_LABOR']);
    });

    it('sin insumos la realización queda CONFIRMADA', function () {
        $programada = DatosLabor::programada($this->parcela, $this->campania);
        $this->postJson(RUTA_LABORES, $programada, $this->admin);

        $this->postJson(RUTA_LABORES."/{$programada['idOperacion']}/realizacion", DatosLabor::realizacion(), $this->tecnico)
            ->assertOk()->assertJson(['estado' => 'CONFIRMADA']);
    });

    it('si la campaña se finalizó, la realización se rechaza y la labor sigue PROGRAMADA', function () {
        $programada = DatosLabor::programada($this->parcela, $this->campania);
        $this->postJson(RUTA_LABORES, $programada, $this->admin);
        GestionFalsa::campania($this->campania, $this->parcela, 'FINALIZADA');

        $this->postJson(RUTA_LABORES."/{$programada['idOperacion']}/realizacion", DatosLabor::realizacion(), $this->tecnico)
            ->assertStatus(422)->assertJson(['codigo' => 'CAMPANIA_FINALIZADA']);
        $this->getJson(RUTA_LABORES."/{$programada['idOperacion']}", $this->admin)->assertJson(['estado' => 'PROGRAMADA']);
    });

    it('una labor que ya no está programada no se realiza otra vez', function () {
        $programada = DatosLabor::programada($this->parcela, $this->campania);
        $this->postJson(RUTA_LABORES, $programada, $this->admin);
        $this->postJson(RUTA_LABORES."/{$programada['idOperacion']}/realizacion", DatosLabor::realizacion(), $this->tecnico)->assertOk();

        $this->postJson(RUTA_LABORES."/{$programada['idOperacion']}/realizacion", DatosLabor::realizacion(), $this->tecnico)
            ->assertStatus(422)->assertJson(['codigo' => 'LABOR_NO_PROGRAMADA']);
    });

    it('la realización de una labor inexistente es 404', function () {
        $this->postJson(RUTA_LABORES.'/'.DatosLabor::uuid().'/realizacion', DatosLabor::realizacion(), $this->tecnico)
            ->assertNotFound()->assertJson(['codigo' => 'LABOR_NO_ENCONTRADA']);
    });
});

describe('Historia 5 — consultar labores', function () {
    it('pagina por cursor ordenando por fechaReferencia descendente', function () {
        foreach (range(1, 30) as $i) {
            $this->postJson(RUTA_LABORES, DatosLabor::realizada($this->parcela, $this->campania, [
                'fechaEjecucion' => DatosLabor::fecha("-{$i} hours"),
            ]), $this->tecnico)->assertCreated();
        }

        $primera = $this->getJson(RUTA_LABORES."?idCampania={$this->campania}", $this->gerente)->assertOk();
        expect($primera->json('items'))->toHaveCount(20)
            ->and($primera->json('siguienteCursor'))->toBeString();
        $fechas = array_column($primera->json('items'), 'fechaReferencia');
        expect($fechas)->toBe(collect($fechas)->sortDesc()->values()->all());

        $segunda = $this->getJson(RUTA_LABORES."?idCampania={$this->campania}&cursor=".$primera->json('siguienteCursor'), $this->gerente)->assertOk();
        $ids = [...array_column($primera->json('items'), 'id'), ...array_column($segunda->json('items'), 'id')];
        expect($segunda->json('items'))->toHaveCount(10)
            ->and(array_unique($ids))->toHaveCount(30);

        $ultima = $segunda->json('siguienteCursor');
        if ($ultima !== null) {
            $this->getJson(RUTA_LABORES."?idCampania={$this->campania}&cursor={$ultima}", $this->gerente)
                ->assertOk()->assertJson(['items' => [], 'siguienteCursor' => null]);
        }
    });

    it('n8n lista las programadas próximas y retrasadas por rango de fechas', function () {
        $campania = DatosLabor::uuid();
        GestionFalsa::campania($campania, $this->parcela);
        $hoy = (new DateTimeImmutable('now', new DateTimeZone('UTC')))->format('Y-m-d');
        $fechas = [
            'manana' => (new DateTimeImmutable('+1 day'))->format('Y-m-d'),
            'en10dias' => (new DateTimeImmutable('+10 days'))->format('Y-m-d'),
        ];
        $ids = [];
        foreach ($fechas as $clave => $fecha) {
            $cuerpo = DatosLabor::programada($this->parcela, $campania, ['fechaProgramada' => $fecha]);
            $ids[$clave] = $cuerpo['idOperacion'];
            $this->postJson(RUTA_LABORES, $cuerpo, $this->admin)->assertCreated();
        }
        $n8n = $this->encabezados(['lectura_operaciones'], 'service-account-n8n');
        $hasta = (new DateTimeImmutable('+2 days'))->format('Y-m-d');

        $proximas = $this->getJson(RUTA_LABORES."?estado=PROGRAMADA&idCampania={$campania}&fechaDesde={$hoy}&fechaHasta={$hasta}&orden=ASC", $n8n)->assertOk();

        expect(array_column($proximas->json('items'), 'id'))->toBe([$ids['manana']]);
    });

    it('un técnico ve las suyas con mias=true y las programadas con estado=PROGRAMADA', function () {
        $mia = DatosLabor::realizada($this->parcela, $this->campania);
        $ajena = DatosLabor::realizada($this->parcela, $this->campania);
        $programada = DatosLabor::programada($this->parcela, $this->campania);
        $this->postJson(RUTA_LABORES, $mia, $this->tecnico)->assertCreated();
        $this->postJson(RUTA_LABORES, $ajena, $this->encabezados(['tecnico_campo'], 'tec-otro'))->assertCreated();
        $this->postJson(RUTA_LABORES, $programada, $this->admin)->assertCreated();

        $mias = $this->getJson(RUTA_LABORES.'?mias=true&idCampania='.$this->campania, $this->tecnico)->assertOk();
        $programadas = $this->getJson(RUTA_LABORES.'?estado=PROGRAMADA&idCampania='.$this->campania, $this->tecnico)->assertOk();

        expect(array_column($mias->json('items'), 'id'))->toBe([$mia['idOperacion']])
            ->and(array_column($programadas->json('items'), 'id'))->toBe([$programada['idOperacion']]);
        $this->getJson(RUTA_LABORES."/{$programada['idOperacion']}", $this->tecnico)->assertOk();
        $this->getJson(RUTA_LABORES."/{$ajena['idOperacion']}", $this->tecnico)->assertForbidden()->assertJson(['codigo' => 'SIN_PERMISO']);
        $this->getJson(RUTA_LABORES."?idCampania={$this->campania}", $this->tecnico)->assertForbidden();
    });

    it('responde 400 sin filtro principal, con cursor manipulado o con fechas invertidas', function (string $consulta) {
        $this->getJson(RUTA_LABORES.$consulta, $this->gerente)->assertStatus(400)->assertJson(['codigo' => 'DATOS_INVALIDOS']);
    })->with([
        'sin filtro' => [''],
        'solo fechas' => ['?fechaDesde=2026-11-01'],
        'cursor inválido' => ['?estado=PROGRAMADA&cursor=no-es-un-cursor'],
        'cursor de otro listado' => ['?estado=CONFIRMADA&cursor='.rtrim(strtr(base64_encode('{"id":{"S":"x"},"estado":{"S":"PROGRAMADA"},"fecha_referencia":{"S":"2026"}}'), '+/', '-_'), '=')],
        'fechas invertidas' => ['?estado=PROGRAMADA&fechaDesde=2026-11-10&fechaHasta=2026-11-01'],
        'límite fuera de rango' => ['?estado=PROGRAMADA&limite=101'],
    ]);

    it('un ID inexistente es 404 LABOR_NO_ENCONTRADA', function () {
        $this->getJson(RUTA_LABORES.'/'.DatosLabor::uuid(), $this->gerente)->assertNotFound()->assertJson(['codigo' => 'LABOR_NO_ENCONTRADA']);
    });

    it('la cuenta de lectura no puede crear labores', function () {
        $this->postJson(RUTA_LABORES, DatosLabor::realizada($this->parcela, $this->campania), $this->encabezados(['lectura_operaciones']))
            ->assertForbidden();
    });
});
