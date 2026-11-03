<?php

use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\ResolveReview\ResolverRevisionCasoUso;
use App\Application\UseCases\ResolveReview\ResolverRevisionEntrada;
use App\Domain\FieldTask\DecisionRevision;
use App\Domain\Shared\ExcepcionDominio;
use App\Infrastructure\Messaging\TopologiaSaga;
use Illuminate\Foundation\Application;
use Illuminate\Testing\TestResponse;
use Tests\Support\DatosLabor;
use Tests\Support\EnParalelo;
use Tests\Support\FlujoSaga;
use Tests\Support\GestionFalsa;
use Tests\Support\RabbitPruebas;

/** Lleva la labor a revisión por un costo rechazado; con $restaurar, la Saga queda COMPENSADA (si no, COMPENSANDO). */
function enRevisionCompensada(FlujoSaga $flujo, bool $restaurar = true): FlujoSaga
{
    $flujo->registrar('2')->descontado('9.70');
    $flujo->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
    $flujo->responder('CostoCampaniaRechazado', ['idCampania' => $flujo->campania, 'codigo' => 'CAMPANIA_NO_ENCONTRADA', 'motivo' => 'No existe.']);
    $flujo->comandoA(TopologiaSaga::COLA_INVENTARIO, 'RestaurarInsumos');
    if ($restaurar) {
        $flujo->responder('InsumosRestaurados', ['sinEfecto' => false, 'items' => []]);
    }

    return $flujo;
}

/** Lleva la labor a revisión con la anulación del costo rechazada: Saga REQUIERE_INTERVENCION. */
function enRevisionConIntervencion(FlujoSaga $flujo): FlujoSaga
{
    $flujo->registrar('2')->descontado('9.70');
    $flujo->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
    foreach ([31, 62, 93] as $segundos) {
        $flujo->vencer($segundos)->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
    }
    $flujo->vencer(124)->comandoA(TopologiaSaga::COLA_GESTION, 'AnularCostoCampania');
    $flujo->responder('AnulacionCostoRechazada', ['idCampania' => $flujo->campania, 'idCosto' => 'c1', 'codigo' => 'CAMPANIA_FINALIZADA', 'motivo' => 'Finalizada.']);

    return $flujo;
}

beforeEach(function () {
    $this->flujo = FlujoSaga::preparar($this);
    $this->admin = $this->encabezados(['administrador'], 'adm-luis');
});

function resolver(FlujoSaga $flujo, array $encabezados, string $decision, ?int $version = null, string $observacion = 'Revisado con gestión'): TestResponse
{
    return test()->postJson("/api/operaciones/v1/labores/{$flujo->idLabor}/resolucion", [
        'decision' => $decision,
        'observacion' => $observacion,
        'version' => $version ?? $flujo->labor()['version'],
    ], $encabezados);
}

it('RECHAZAR con Saga COMPENSADA deja la labor RECHAZADA con su resolución y la audita (escenario 1)', function () {
    $flujo = enRevisionCompensada($this->flujo);

    resolver($flujo, $this->admin, 'RECHAZAR')
        ->assertOk()
        ->assertJson([
            'estado' => 'RECHAZADA',
            'motivo' => ['codigo' => 'RECHAZADA_EN_REVISION'],
            'resolucion' => [
                'decision' => 'RECHAZAR',
                'observacion' => 'Revisado con gestión',
                'administrador' => ['id' => 'adm-luis', 'nombre' => 'Usuario adm-luis'],
                'motivoAnterior' => ['codigo' => 'COSTO_RECHAZADO'],
            ],
            'idsSagaAnteriores' => [],
        ]);

    expect(FlujoSaga::auditorias('LABOR', $flujo->idLabor))->toContain('RESOLVER_LABOR');
    $flujo->sinComandos();
});

it('REINTENTAR crea una Saga nueva que llega hasta CONFIRMADA (escenario 2, CE-REV-02)', function () {
    $flujo = enRevisionCompensada($this->flujo);
    $sagaAnterior = $flujo->idSaga;

    $respuesta = resolver($flujo, $this->admin, 'REINTENTAR')->assertOk()
        ->assertJson(['estado' => 'PENDIENTE', 'motivo' => null, 'idsSagaAnteriores' => [$sagaAnterior], 'resolucion' => ['decision' => 'REINTENTAR']]);
    $flujo->idSaga = (string) $respuesta->json('idSaga');
    expect($flujo->idSaga)->not->toBe($sagaAnterior);

    $descontar = $flujo->comandoA(TopologiaSaga::COLA_INVENTARIO, 'DescontarInsumos');
    expect($descontar['datos']['idLabor'])->toBe($flujo->idLabor);
    $flujo->descontado('9.70');
    $flujo->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
    $flujo->responder('CostoCampaniaRegistrado', ['idCampania' => $flujo->campania, 'idCosto' => DatosLabor::uuid(), 'monto' => '9.70']);

    expect($flujo->labor())->toMatchArray(['estado' => 'CONFIRMADA', 'idSaga' => $flujo->idSaga, 'idsSagaAnteriores' => [$sagaAnterior]]);
});

it('una respuesta tardía de la Saga anterior no afecta a la labor reintentada', function () {
    $flujo = enRevisionCompensada($this->flujo);
    $sagaAnterior = $flujo->idSaga;
    resolver($flujo, $this->admin, 'REINTENTAR')->assertOk();
    RabbitPruebas::leer(TopologiaSaga::COLA_INVENTARIO);

    RabbitPruebas::responder('InsumosRestaurados', $sagaAnterior, ['idLabor' => $flujo->idLabor, 'sinEfecto' => true, 'items' => []]);
    RabbitPruebas::procesarRespuestas(1);

    expect($flujo->labor()['estado'])->toBe('PENDIENTE');
});

it('CONFIRMAR con Saga REQUIERE_INTERVENCION deja la labor CONFIRMADA (escenario 3)', function () {
    $flujo = enRevisionConIntervencion($this->flujo);

    resolver($flujo, $this->admin, 'CONFIRMAR')->assertOk()
        ->assertJson(['estado' => 'CONFIRMADA', 'motivo' => null, 'resolucion' => ['motivoAnterior' => ['codigo' => 'ANULACION_COSTO_RECHAZADA']]]);
});

it('una decisión que no corresponde es 422 DECISION_NO_PERMITIDA con las permitidas (escenario 4)', function () {
    $flujo = enRevisionCompensada($this->flujo);

    resolver($flujo, $this->admin, 'CONFIRMAR')->assertStatus(422)
        ->assertJson(['codigo' => 'DECISION_NO_PERMITIDA', 'detalles' => [['decisionesPermitidas' => ['RECHAZAR', 'REINTENTAR']]]]);
});

it('con la Saga todavía compensando es 409 SAGA_EN_CURSO (escenario 5)', function () {
    $flujo = enRevisionCompensada($this->flujo, restaurar: false);

    resolver($flujo, $this->admin, 'RECHAZAR')->assertStatus(409)->assertJson(['codigo' => 'SAGA_EN_CURSO']);
});

it('una labor que no está en revisión es 422 LABOR_NO_EN_REVISION (escenario 6)', function () {
    $flujo = $this->flujo->registrar('2');

    resolver($flujo, $this->admin, 'RECHAZAR')->assertStatus(422)->assertJson(['codigo' => 'LABOR_NO_EN_REVISION']);
});

it('REINTENTAR en una campaña ya finalizada es 422 y la labor no cambia (escenario 7)', function () {
    $flujo = enRevisionCompensada($this->flujo);
    GestionFalsa::campania($flujo->campania, $flujo->parcela, 'FINALIZADA');

    resolver($flujo, $this->admin, 'REINTENTAR')->assertStatus(422)->assertJson(['codigo' => 'CAMPANIA_FINALIZADA']);
    expect($flujo->estadoLabor())->toBe('PENDIENTE_REVISION/COSTO_RECHAZADO');
    $flujo->sinComandos();
});

it('REINTENTAR sigue aunque gestión no responda: la Saga lo resolverá', function () {
    $flujo = enRevisionCompensada($this->flujo);
    GestionFalsa::disponible(false);

    $flujo->idSaga = (string) resolver($flujo, $this->admin, 'REINTENTAR')->assertOk()->assertJson(['estado' => 'PENDIENTE'])->json('idSaga');
    $flujo->comandoA(TopologiaSaga::COLA_INVENTARIO, 'DescontarInsumos');
});

it('solo un administrador resuelve (escenario 8)', function (string $rol) {
    $flujo = enRevisionCompensada($this->flujo);

    resolver($flujo, $this->encabezados([$rol]), 'RECHAZAR')->assertForbidden()->assertJson(['codigo' => 'SIN_PERMISO']);
})->with(['gerencia', 'tecnico_campo', 'lectura_operaciones']);

it('responde 400 con observación vacía o larga, decisión desconocida o sin versión', function (array $cuerpo) {
    $flujo = enRevisionCompensada($this->flujo);

    $this->postJson("/api/operaciones/v1/labores/{$flujo->idLabor}/resolucion", $cuerpo, $this->admin)
        ->assertStatus(400)->assertJson(['codigo' => 'DATOS_INVALIDOS']);
})->with([
    'observación vacía' => [['decision' => 'RECHAZAR', 'observacion' => '   ', 'version' => 2]],
    'observación de 501' => [['decision' => 'RECHAZAR', 'observacion' => str_repeat('a', 501), 'version' => 2]],
    'decisión desconocida' => [['decision' => 'ANULAR', 'observacion' => 'x', 'version' => 2]],
    'sin versión' => [['decision' => 'RECHAZAR', 'observacion' => 'x']],
]);

it('con una versión vieja es 409 CONFLICTO_CONCURRENCIA', function () {
    $flujo = enRevisionCompensada($this->flujo);

    resolver($flujo, $this->admin, 'RECHAZAR', version: 0)->assertStatus(409)->assertJson(['codigo' => 'CONFLICTO_CONCURRENCIA']);
});

it('una labor inexistente es 404', function () {
    $this->postJson('/api/operaciones/v1/labores/'.DatosLabor::uuid().'/resolucion', ['decision' => 'RECHAZAR', 'observacion' => 'x', 'version' => 0], $this->admin)
        ->assertNotFound()->assertJson(['codigo' => 'LABOR_NO_ENCONTRADA']);
});

it('dos administradores que resuelven a la vez con la misma versión: uno 200 y el otro 409 (escenario 9)', function () {
    $flujo = enRevisionCompensada($this->flujo);
    $idLabor = $flujo->idLabor;
    $version = $flujo->labor()['version'];

    $resultados = EnParalelo::ejecutar(2, function (Application $app, int $i) use ($idLabor, $version) {
        try {
            $app->make(ResolverRevisionCasoUso::class)->ejecutar(
                new ResolverRevisionEntrada($idLabor, DecisionRevision::RECHAZAR, "Admin {$i}", $version),
                new UsuarioAutenticado("adm-{$i}", 'Admin', ['administrador']),
            );

            return 'aceptada';
        } catch (ExcepcionDominio $e) {
            return $e->codigo;
        }
    });

    $valores = array_map(fn (array $r) => $r['valor'] ?? $r['error'], $resultados);
    sort($valores);
    expect($valores)->toBe(['CONFLICTO_CONCURRENCIA', 'aceptada'])
        ->and(array_count_values(FlujoSaga::auditorias('LABOR', $idLabor))['RESOLVER_LABOR'])->toBe(1);
});
