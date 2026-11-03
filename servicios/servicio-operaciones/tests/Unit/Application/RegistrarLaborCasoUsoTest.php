<?php

require_once __DIR__.'/Dobles.php';

use App\Application\Security\SinPermiso;
use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\RegisterFieldTask\CreacionLabor;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborCasoUso;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborEntrada;
use App\Application\UseCases\RegisterFieldTask\VerificadorCampania;
use App\Application\UseCases\ScheduleFieldTask\ProgramarLaborCasoUso;
use App\Application\UseCases\ScheduleFieldTask\ProgramarLaborEntrada;
use App\Domain\FieldTask\CampaniaConsultada;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\Responsable;
use App\Domain\FieldTask\TipoLabor;
use App\Domain\FieldTask\ValidacionCampania;
use App\Domain\Shared\ExcepcionDominio;
use Psr\Log\NullLogger;
use Tests\Support\RelojFijo;
use Tests\Unit\Application\AuditoriaEnMemoria;
use Tests\Unit\Application\PasarelaCampaniaFalsa;
use Tests\Unit\Application\RepositorioLaborEnMemoria;
use Tests\Unit\Application\UnidadTrabajoDirecta;

use function Tests\Unit\Application\iniciarSagaEnMemoria;

beforeEach(function () {
    $this->repositorio = new RepositorioLaborEnMemoria;
    $this->auditoria = new AuditoriaEnMemoria;
    $this->pasarela = new PasarelaCampaniaFalsa;
    $this->pasarela->campanias['c1'] = new CampaniaConsultada('c1', 'p1', 'EN_CURSO');
    $creacion = new CreacionLabor($this->repositorio, new UnidadTrabajoDirecta, $this->auditoria,
        new VerificadorCampania($this->pasarela, new NullLogger), new RelojFijo('2026-11-02T14:00:00Z'),
        iniciarSagaEnMemoria($this->auditoria));
    $this->registrar = new RegistrarLaborCasoUso($creacion);
    $this->programar = new ProgramarLaborCasoUso($creacion);
    $this->tecnico = new UsuarioAutenticado('tec-1', 'Ana Quispe', ['tecnico_campo']);
});

function entradaRealizada(array $cambios = []): RegistrarLaborEntrada
{
    $utc = new DateTimeZone('UTC');

    return new RegistrarLaborEntrada(...array_merge([
        'idOperacion' => 'op-1',
        'fechaCreacion' => new DateTimeImmutable('2026-11-02T13:58:00Z', $utc),
        'tipoLabor' => TipoLabor::FERTILIZACION,
        'idParcela' => 'p1',
        'idCampania' => 'c1',
        'fechaEjecucion' => new DateTimeImmutable('2026-11-02T13:30:00Z', $utc),
        'observaciones' => null,
        'insumos' => [['idInsumo' => 'i1', 'cantidad' => '100'], ['idInsumo' => 'i2', 'cantidad' => '2.5']],
    ], $cambios));
}

function codigoError(callable $accion): string
{
    try {
        $accion();
    } catch (ExcepcionDominio $e) {
        return $e->tipo->value.':'.$e->codigo;
    }

    return 'SIN_ERROR';
}

it('registra la labor con insumos como PENDIENTE, con el responsable del token y su auditoría', function () {
    $resultado = $this->registrar->ejecutar(entradaRealizada(), $this->tecnico);

    expect($resultado->repetida)->toBeFalse()
        ->and($resultado->labor->estado)->toBe(EstadoLabor::PENDIENTE)
        ->and($resultado->labor->responsable->nombre)->toBe('Ana Quispe')
        ->and($this->repositorio->labores)->toHaveKey('op-1')
        ->and($resultado->labor->idSaga)->toBeString()
        ->and($this->auditoria->registros)->toBe([
            ['actor' => 'tec-1', 'accion' => 'REGISTRAR_LABOR', 'entidad' => 'LABOR', 'idEntidad' => 'op-1'],
            ['actor' => 'servicio-operaciones', 'accion' => 'INICIAR_SAGA', 'entidad' => 'SAGA', 'idEntidad' => $resultado->labor->idSaga],
        ]);
});

it('una repetición con el mismo contenido devuelve la labor sin consultar gestión ni auditar', function () {
    $this->registrar->ejecutar(entradaRealizada(), $this->tecnico);
    // Mismos insumos en otro orden y cantidades escritas distinto: misma operación
    $repetida = $this->registrar->ejecutar(entradaRealizada(['insumos' => [
        ['idInsumo' => 'i2', 'cantidad' => '2.500'], ['idInsumo' => 'i1', 'cantidad' => '100.0'],
    ]]), $this->tecnico);

    expect($repetida->repetida)->toBeTrue()
        ->and($this->pasarela->consultas)->toBe(1)
        ->and($this->auditoria->registros)->toHaveCount(2);
});

it('el mismo idOperacion con otro contenido u otro usuario es CONFLICTO_IDEMPOTENCIA', function (array $cambios, ?UsuarioAutenticado $otro) {
    $this->registrar->ejecutar(entradaRealizada(), $this->tecnico);

    expect(codigoError(fn () => $this->registrar->ejecutar(entradaRealizada($cambios), $otro ?? $this->tecnico)))
        ->toBe('CONFLICTO:CONFLICTO_IDEMPOTENCIA');
})->with([
    'otra cantidad' => [['insumos' => [['idInsumo' => 'i1', 'cantidad' => '101']]], null],
    'otro usuario' => [[], new UsuarioAutenticado('tec-2', 'Otro', ['tecnico_campo'])],
]);

it('si otra solicitud gana la carrera, responde como repetición', function () {
    $ganadora = $this->registrar->ejecutar(entradaRealizada(), $this->tecnico)->labor;
    $this->repositorio->labores = [];
    $this->repositorio->ganadoraCarrera = $ganadora;

    $resultado = $this->registrar->ejecutar(entradaRealizada(), $this->tecnico);

    expect($resultado->repetida)->toBeTrue()->and($this->auditoria->registros)->toHaveCount(2);
});

it('traduce cada respuesta de gestión (RQ-LAB-05)', function (?CampaniaConsultada $campania, bool $disponible, string $esperado) {
    $this->pasarela->campanias = $campania === null ? [] : ['c1' => $campania];
    $this->pasarela->disponible = $disponible;

    $resultado = codigoError(fn () => $this->registrar->ejecutar(entradaRealizada(), $this->tecnico));
    if ($resultado === 'SIN_ERROR') {
        $labor = $this->repositorio->labores['op-1'];
        $resultado = $labor->estado->value.'/'.$labor->validacionCampania->value;
    }

    expect($resultado)->toBe($esperado);
})->with([
    'en curso' => [new CampaniaConsultada('c1', 'p1', 'EN_CURSO'), true, 'PENDIENTE/VALIDADA'],
    'planificada' => [new CampaniaConsultada('c1', 'p1', 'PLANIFICADA'), true, 'PENDIENTE/VALIDADA'],
    'finalizada' => [new CampaniaConsultada('c1', 'p1', 'FINALIZADA'), true, 'REGLA_NEGOCIO:CAMPANIA_FINALIZADA'],
    'otra parcela' => [new CampaniaConsultada('c1', 'p9', 'EN_CURSO'), true, 'REGLA_NEGOCIO:PARCELA_NO_CORRESPONDE'],
    'inexistente' => [null, true, 'NO_ENCONTRADO:CAMPANIA_NO_ENCONTRADA'],
    'gestión caída' => [null, false, 'PENDIENTE/PENDIENTE'],
]);

it('lo rechazado en el momento no se guarda (RQ-LAB-13)', function () {
    $this->pasarela->campanias['c1'] = new CampaniaConsultada('c1', 'p1', 'FINALIZADA');
    codigoError(fn () => $this->registrar->ejecutar(entradaRealizada(), $this->tecnico));

    expect($this->repositorio->labores)->toBe([])->and($this->auditoria->registros)->toBe([]);
});

it('valida las fechas antes de consultar gestión', function () {
    $entrada = entradaRealizada(['fechaEjecucion' => new DateTimeImmutable('2026-11-02T15:00:00Z')]);

    expect(codigoError(fn () => $this->registrar->ejecutar($entrada, $this->tecnico)))->toBe('REGLA_NEGOCIO:FECHA_EJECUCION_INVALIDA')
        ->and($this->pasarela->consultas)->toBe(0);
});

it('solo un técnico de campo registra una labor realizada', function () {
    expect(fn () => $this->registrar->ejecutar(entradaRealizada(), new UsuarioAutenticado('a', 'A', ['administrador', 'gerencia'])))
        ->toThrow(SinPermiso::class);
});

it('programa con administrador o técnico; no con gerencia', function () {
    $entrada = new ProgramarLaborEntrada('op-9', new DateTimeImmutable('2026-11-02T13:00:00Z'), TipoLabor::SIEMBRA, 'p1', 'c1', '2026-11-20', null);

    $resultado = $this->programar->ejecutar($entrada, new UsuarioAutenticado('adm', 'Luis', ['administrador']));

    expect($resultado->labor->estado)->toBe(EstadoLabor::PROGRAMADA)
        ->and($resultado->labor->programadaPor)->toEqual(new Responsable('adm', 'Luis'))
        ->and($this->auditoria->registros[0]['accion'])->toBe('PROGRAMAR_LABOR')
        ->and(fn () => $this->programar->ejecutar($entrada, new UsuarioAutenticado('g', 'G', ['gerencia'])))->toThrow(SinPermiso::class);
});

it('normaliza los UUID a minúsculas', function () {
    $resultado = $this->registrar->ejecutar(entradaRealizada(['idOperacion' => 'OP-1', 'idCampania' => 'C1', 'idParcela' => 'P1']), $this->tecnico);

    expect($resultado->labor)->toBeInstanceOf(LaborAgricola::class)
        ->and($resultado->labor->id)->toBe('op-1')
        ->and($resultado->labor->validacionCampania)->toBe(ValidacionCampania::VALIDADA);
});
