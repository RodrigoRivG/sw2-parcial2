<?php

use App\Application\Contracts\PasarelaCampania;
use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\RegisterFieldTask\RealizarLaborCasoUso;
use App\Application\UseCases\RegisterFieldTask\RealizarLaborEntrada;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborCasoUso;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborEntrada;
use App\Domain\FieldTask\CampaniaConsultada;
use App\Domain\FieldTask\TipoLabor;
use App\Domain\Shared\ExcepcionDominio;
use App\Infrastructure\Persistence\DynamoDb\NombresTablas;
use Aws\DynamoDb\DynamoDbClient;
use Illuminate\Foundation\Application;
use Tests\Support\DatosLabor;
use Tests\Support\EnParalelo;
use Tests\Support\GestionFalsa;

beforeEach(function () {
    GestionFalsa::instalar();
    $this->parcela = DatosLabor::uuid();
    $this->campania = DatosLabor::uuid();
    GestionFalsa::campania($this->campania, $this->parcela);
    $this->tecnico = $this->encabezados(['tecnico_campo'], 'tec-ana');
});

function contarAuditorias(string $idLabor, string $accion): int
{
    $resultado = app(DynamoDbClient::class)->query([
        'TableName' => app(NombresTablas::class)->de('registros_auditoria'),
        'IndexName' => 'gsi_entidad',
        'KeyConditionExpression' => 'entidad_id = :e',
        'FilterExpression' => 'accion = :a',
        'ExpressionAttributeValues' => [':e' => ['S' => "LABOR#{$idLabor}"], ':a' => ['S' => $accion]],
    ]);

    return count($resultado['Items']);
}

/** En los procesos hijos, gestión se simula con una pasarela fija (Http::fake no cruza el fork). */
function pasarelaFija(string $idCampania, string $idParcela): Closure
{
    return fn (Application $app) => $app->instance(PasarelaCampania::class, new class($idCampania, $idParcela) implements PasarelaCampania
    {
        public function __construct(private string $idCampania, private string $idParcela) {}

        public function consultar(string $idCampania): ?CampaniaConsultada
        {
            return new CampaniaConsultada($this->idCampania, $this->idParcela, 'EN_CURSO');
        }
    });
}

it('operación nueva → 201; repetida → 200 con el estado actual y sin consultar gestión ni auditar', function () {
    $cuerpo = DatosLabor::realizada($this->parcela, $this->campania, ['insumos' => DatosLabor::insumos('10')]);

    $this->postJson('/api/operaciones/v1/labores', $cuerpo, $this->tecnico)->assertCreated();
    $consultas = GestionFalsa::consultas();
    $this->postJson('/api/operaciones/v1/labores', $cuerpo, $this->tecnico)
        ->assertOk()
        ->assertJson(['id' => $cuerpo['idOperacion'], 'estado' => 'PENDIENTE']);

    expect(GestionFalsa::consultas())->toBe($consultas)
        ->and(contarAuditorias($cuerpo['idOperacion'], 'REGISTRAR_LABOR'))->toBe(1);
});

it('mismo idOperacion con otro contenido u otro usuario → 409 y la labor no cambia', function (Closure $cambiar) {
    $cuerpo = DatosLabor::realizada($this->parcela, $this->campania);
    $this->postJson('/api/operaciones/v1/labores', $cuerpo, $this->tecnico)->assertCreated();
    [$otroCuerpo, $usuario] = $cambiar($cuerpo, $this->encabezados(['tecnico_campo'], 'tec-otro'));

    $this->postJson('/api/operaciones/v1/labores', $otroCuerpo, $usuario ?? $this->tecnico)
        ->assertStatus(409)->assertJson(['codigo' => 'CONFLICTO_IDEMPOTENCIA']);
    $this->getJson("/api/operaciones/v1/labores/{$cuerpo['idOperacion']}", $this->encabezados(['gerencia']))
        ->assertJson(['tipoLabor' => 'RIEGO', 'responsable' => ['id' => 'tec-ana'], 'version' => 0]);
})->with([
    'otro tipo' => fn (array $c, array $otro) => [[...$c, 'tipoLabor' => 'COSECHA'], null],
    'otra parcela' => fn (array $c, array $otro) => [[...$c, 'idParcela' => DatosLabor::uuid()], null],
    'otro usuario' => fn (array $c, array $otro) => [$c, $otro],
]);

it('lo rechazado no se guarda: al reenviarlo se vuelve a validar', function () {
    GestionFalsa::campania($this->campania, $this->parcela, 'FINALIZADA');
    $cuerpo = DatosLabor::realizada($this->parcela, $this->campania);

    $this->postJson('/api/operaciones/v1/labores', $cuerpo, $this->tecnico)->assertStatus(422);
    $consultas = GestionFalsa::consultas();
    $this->postJson('/api/operaciones/v1/labores', $cuerpo, $this->tecnico)->assertStatus(422)->assertJson(['codigo' => 'CAMPANIA_FINALIZADA']);

    expect(GestionFalsa::consultas())->toBe($consultas + 1);
});

it('la realización repetida → 200 sin cambios; con otro contenido → 409; con el UUID de la creación → 409', function () {
    $programada = DatosLabor::programada($this->parcela, $this->campania);
    $this->postJson('/api/operaciones/v1/labores', $programada, $this->encabezados(['administrador']))->assertCreated();
    $ruta = "/api/operaciones/v1/labores/{$programada['idOperacion']}/realizacion";
    $realizacion = DatosLabor::realizacion(['insumos' => DatosLabor::insumos('5')]);

    $this->postJson($ruta, $realizacion, $this->tecnico)->assertOk()->assertJson(['version' => 1]);
    $this->postJson($ruta, $realizacion, $this->tecnico)->assertOk()->assertJson(['version' => 1]);
    $this->postJson($ruta, [...$realizacion, 'insumos' => DatosLabor::insumos('6')], $this->tecnico)
        ->assertStatus(409)->assertJson(['codigo' => 'CONFLICTO_IDEMPOTENCIA']);
    $this->postJson($ruta, [...DatosLabor::realizacion(), 'idOperacion' => $programada['idOperacion']], $this->tecnico)
        ->assertStatus(409)->assertJson(['codigo' => 'CONFLICTO_IDEMPOTENCIA']);

    expect(contarAuditorias($programada['idOperacion'], 'REALIZAR_LABOR'))->toBe(1);
});

it('20 envíos simultáneos del mismo idOperacion crean una sola labor y una sola auditoría (CE-LAB-02)', function () {
    $idOperacion = DatosLabor::uuid();
    $utc = new DateTimeZone('UTC');
    $creacion = new DateTimeImmutable(DatosLabor::fecha('-1 minute'), $utc);
    $ejecucion = new DateTimeImmutable(DatosLabor::fecha('-30 minutes'), $utc);
    $parcela = $this->parcela;
    $campania = $this->campania;

    $resultados = EnParalelo::ejecutar(20, function (Application $app) use ($idOperacion, $creacion, $ejecucion, $parcela, $campania) {
        $resultado = $app->make(RegistrarLaborCasoUso::class)->ejecutar(
            new RegistrarLaborEntrada($idOperacion, $creacion, TipoLabor::RIEGO, $parcela, $campania, $ejecucion, null,
                [['idInsumo' => '8a1c0f3e-0000-4000-8000-000000000001', 'cantidad' => '3']]),
            new UsuarioAutenticado('tec-ana', 'Ana', ['tecnico_campo']),
        );

        return $resultado->repetida ? 'repetida' : 'nueva';
    }, pasarelaFija($campania, $parcela));

    // El orden en que terminan los procesos varía: se comparan los conteos, no su orden
    $conteo = array_count_values(array_map(fn (array $r) => $r['valor'] ?? $r['error'], $resultados));
    ksort($conteo);
    expect($conteo)->toBe(['nueva' => 1, 'repetida' => 19])
        ->and(contarAuditorias($idOperacion, 'REGISTRAR_LABOR'))->toBe(1);
});

it('dos realizaciones simultáneas con distinto idOperacion: una se acepta y la otra es LABOR_NO_PROGRAMADA', function () {
    $programada = DatosLabor::programada($this->parcela, $this->campania);
    $this->postJson('/api/operaciones/v1/labores', $programada, $this->encabezados(['administrador']))->assertCreated();
    $idLabor = $programada['idOperacion'];
    $utc = new DateTimeZone('UTC');
    $creacion = new DateTimeImmutable(DatosLabor::fecha('-1 minute'), $utc);

    $resultados = EnParalelo::ejecutar(2, function (Application $app, int $numero) use ($idLabor, $creacion) {
        try {
            $app->make(RealizarLaborCasoUso::class)->ejecutar(
                new RealizarLaborEntrada($idLabor, DatosLabor::uuid(), $creacion, $creacion, null, []),
                new UsuarioAutenticado("tec-{$numero}", 'Técnico', ['tecnico_campo']),
            );

            return 'aceptada';
        } catch (ExcepcionDominio $e) {
            return $e->codigo;
        }
    }, pasarelaFija($this->campania, $this->parcela));

    $valores = array_map(fn (array $r) => $r['valor'] ?? $r['error'], $resultados);
    sort($valores);
    expect($valores)->toBe(['LABOR_NO_PROGRAMADA', 'aceptada'])
        ->and(contarAuditorias($idLabor, 'REALIZAR_LABOR'))->toBe(1);
});
