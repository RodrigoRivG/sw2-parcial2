<?php

use App\Application\Contracts\PasarelaCampania;
use App\Application\Contracts\Reloj;
use App\Application\UseCases\RevalidateCampaign\RevalidarCampaniasCasoUso;
use App\Domain\FieldTask\CampaniaConsultada;
use App\Infrastructure\Persistence\DynamoDb\NombresTablas;
use Aws\DynamoDb\DynamoDbClient;
use Illuminate\Foundation\Application;
use Tests\Support\DatosLabor;
use Tests\Support\EnParalelo;
use Tests\Support\GestionFalsa;
use Tests\Support\RelojFijo;

beforeEach(function () {
    GestionFalsa::instalar();
    $this->parcela = DatosLabor::uuid();
    $this->campania = DatosLabor::uuid();
    GestionFalsa::campania($this->campania, $this->parcela);
    $this->tecnico = $this->encabezados(['tecnico_campo'], 'tec-ana');
    $this->gerente = $this->encabezados(['gerencia']);
});

/** Registra una labor con gestión caída y devuelve su id. */
function registrarConGestionCaida(array $cuerpo, array $encabezados): string
{
    GestionFalsa::disponible(false);
    test()->postJson('/api/operaciones/v1/labores', $cuerpo, $encabezados)
        ->assertCreated()
        ->assertJson(['estado' => 'PENDIENTE', 'validacionCampania' => 'PENDIENTE']);
    GestionFalsa::disponible(true);

    return $cuerpo['idOperacion'];
}

/** Ejecuta la tarea programada como si el reloj marcara ahora + $intervalo. */
function correrTareaEn(string $intervalo): void
{
    app()->instance(Reloj::class, new RelojFijo(DatosLabor::fecha($intervalo)));
    test()->artisan('labores:revalidar-campanias')->assertSuccessful();
}

function auditoriasValidacion(string $idLabor): int
{
    $resultado = app(DynamoDbClient::class)->query([
        'TableName' => app(NombresTablas::class)->de('registros_auditoria'),
        'IndexName' => 'gsi_entidad',
        'KeyConditionExpression' => 'entidad_id = :e',
        'FilterExpression' => 'accion = :a',
        'ExpressionAttributeValues' => [':e' => ['S' => "LABOR#{$idLabor}"], ':a' => ['S' => 'VALIDAR_CAMPANIA']],
    ]);

    return count($resultado['Items']);
}

it('acepta la labor como PENDIENTE si gestión no responde, responde 5xx, 401 o 403', function (?int $estado) {
    if ($estado === null) {
        GestionFalsa::disponible(false);
    } else {
        GestionFalsa::responderError($estado);
    }

    $this->postJson('/api/operaciones/v1/labores', DatosLabor::realizada($this->parcela, $this->campania), $this->tecnico)
        ->assertCreated()
        ->assertJson(['estado' => 'PENDIENTE', 'validacionCampania' => 'PENDIENTE']);
})->with(['sin respuesta' => [null], '500' => [500], '503' => [503], '401' => [401], '403' => [403]]);

it('cuando gestión vuelve, cada labor pasa al estado que le corresponde', function () {
    $sinInsumos = registrarConGestionCaida(DatosLabor::realizada($this->parcela, $this->campania), $this->tecnico);
    $conInsumos = registrarConGestionCaida(DatosLabor::realizada($this->parcela, $this->campania, ['insumos' => DatosLabor::insumos('3')]), $this->tecnico);
    $programada = registrarConGestionCaida(DatosLabor::programada($this->parcela, $this->campania), $this->encabezados(['administrador']));

    correrTareaEn('+2 minutes');

    foreach ([$sinInsumos => 'CONFIRMADA', $conInsumos => 'PENDIENTE', $programada => 'PROGRAMADA'] as $id => $estado) {
        $this->getJson("/api/operaciones/v1/labores/{$id}", $this->gerente)
            ->assertJson(['estado' => $estado, 'validacionCampania' => 'VALIDADA', 'version' => 1]);
        expect(auditoriasValidacion($id))->toBe(1);
    }
});

it('si la campaña resultó finalizada, inexistente o de otra parcela, la labor queda RECHAZADA con su motivo', function (Closure $preparar, string $codigo) {
    $id = registrarConGestionCaida($preparar($this->parcela, $this->campania), $this->tecnico);

    correrTareaEn('+2 minutes');

    $this->getJson("/api/operaciones/v1/labores/{$id}", $this->gerente)
        ->assertJson(['estado' => 'RECHAZADA', 'validacionCampania' => 'VALIDADA', 'motivo' => ['codigo' => $codigo]]);
})->with([
    'finalizada' => [function ($parcela, $campania) {
        GestionFalsa::campania($campania, $parcela, 'FINALIZADA');

        return DatosLabor::realizada($parcela, $campania);
    }, 'CAMPANIA_FINALIZADA'],
    'inexistente' => [fn ($parcela) => DatosLabor::realizada($parcela, DatosLabor::uuid()), 'CAMPANIA_NO_ENCONTRADA'],
    'otra parcela' => [fn ($parcela, $campania) => DatosLabor::realizada(DatosLabor::uuid(), $campania), 'PARCELA_NO_CORRESPONDE'],
]);

it('si gestión sigue caída, pospone el próximo intento sin perder la labor', function () {
    $id = registrarConGestionCaida(DatosLabor::realizada($this->parcela, $this->campania), $this->tecnico);
    GestionFalsa::disponible(false);

    correrTareaEn('+30 seconds');
    $antes = GestionFalsa::consultas();
    correrTareaEn('+2 minutes');
    correrTareaEn('+3 minutes');

    // A los 30 s todavía no vence; a los 2 min se intenta y pospone a +2 min; a los 3 min no vence otra vez
    expect(GestionFalsa::consultas() - $antes)->toBe(1);
    $this->getJson("/api/operaciones/v1/labores/{$id}", $this->gerente)
        ->assertJson(['estado' => 'PENDIENTE', 'validacionCampania' => 'PENDIENTE']);

    GestionFalsa::disponible(true);
    correrTareaEn('+5 minutes');
    $this->getJson("/api/operaciones/v1/labores/{$id}", $this->gerente)->assertJson(['estado' => 'CONFIRMADA']);
});

it('dos ejecuciones simultáneas validan cada labor una sola vez', function () {
    $id = registrarConGestionCaida(DatosLabor::realizada($this->parcela, $this->campania), $this->tecnico);
    $ahora = DatosLabor::fecha('+2 minutes');
    $parcela = $this->parcela;
    $campania = $this->campania;

    $resultados = EnParalelo::ejecutar(2, fn (Application $app) => $app->make(RevalidarCampaniasCasoUso::class)->ejecutar(),
        function (Application $app) use ($ahora, $parcela, $campania) {
            $app->instance(Reloj::class, new RelojFijo($ahora));
            $app->instance(PasarelaCampania::class, new class($campania, $parcela) implements PasarelaCampania
            {
                public function __construct(private string $c, private string $p) {}

                public function consultar(string $idCampania): ?CampaniaConsultada
                {
                    return new CampaniaConsultada($this->c, $this->p, 'EN_CURSO');
                }
            });
        });

    expect(array_column($resultados, 'ok'))->toBe([true, true])
        ->and(auditoriasValidacion($id))->toBe(1);
    $this->getJson("/api/operaciones/v1/labores/{$id}", $this->gerente)->assertJson(['estado' => 'CONFIRMADA', 'version' => 1]);
});
