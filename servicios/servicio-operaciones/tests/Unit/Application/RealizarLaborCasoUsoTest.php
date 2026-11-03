<?php

require_once __DIR__.'/Dobles.php';

use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\RegisterFieldTask\RealizarLaborCasoUso;
use App\Application\UseCases\RegisterFieldTask\RealizarLaborEntrada;
use App\Application\UseCases\RegisterFieldTask\VerificadorCampania;
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
    $utc = new DateTimeZone('UTC');
    $this->repositorio = new RepositorioLaborEnMemoria;
    $this->repositorio->labores['l1'] = LaborAgricola::programar('l1', 'h', TipoLabor::FERTILIZACION, 'p1', 'c1', '2026-11-20',
        new DateTimeImmutable('2026-11-01T10:00:00Z', $utc), null, new Responsable('adm', 'Luis'), ValidacionCampania::VALIDADA,
        new DateTimeImmutable('2026-11-01T10:00:00Z', $utc));
    $this->auditoria = new AuditoriaEnMemoria;
    $this->pasarela = new PasarelaCampaniaFalsa;
    $this->pasarela->campanias['c1'] = new CampaniaConsultada('c1', 'p1', 'EN_CURSO');
    $this->realizar = new RealizarLaborCasoUso($this->repositorio, new UnidadTrabajoDirecta, $this->auditoria,
        new VerificadorCampania($this->pasarela, new NullLogger), new RelojFijo('2026-11-20T12:00:00Z'),
        iniciarSagaEnMemoria($this->auditoria));
    $this->tecnico = new UsuarioAutenticado('tec-1', 'Ana', ['tecnico_campo']);
});

function realizacion(array $cambios = []): RealizarLaborEntrada
{
    $utc = new DateTimeZone('UTC');

    return new RealizarLaborEntrada(...array_merge([
        'idLabor' => 'l1',
        'idOperacion' => 'op-2',
        'fechaCreacion' => new DateTimeImmutable('2026-11-20T11:00:00Z', $utc),
        'fechaEjecucion' => new DateTimeImmutable('2026-11-20T10:00:00Z', $utc),
        'observaciones' => null,
        'insumos' => [['idInsumo' => 'i1', 'cantidad' => '50']],
    ], $cambios));
}

function codigoRealizacion(callable $accion): string
{
    try {
        $accion();
    } catch (ExcepcionDominio $e) {
        return $e->codigo;
    }

    return 'SIN_ERROR';
}

it('realiza la labor programada y la audita', function () {
    $resultado = $this->realizar->ejecutar(realizacion(), $this->tecnico);

    expect($resultado->repetida)->toBeFalse()
        ->and($this->repositorio->labores['l1']->estado)->toBe(EstadoLabor::PENDIENTE)
        ->and($this->repositorio->labores['l1']->responsable->id)->toBe('tec-1')
        ->and($this->auditoria->registros[0]['accion'])->toBe('REALIZAR_LABOR');
});

it('la misma realización repetida devuelve la labor; con otro contenido es conflicto', function () {
    $this->realizar->ejecutar(realizacion(), $this->tecnico);

    expect($this->realizar->ejecutar(realizacion(), $this->tecnico)->repetida)->toBeTrue()
        ->and(array_column($this->auditoria->registros, 'accion'))->toBe(['REALIZAR_LABOR', 'INICIAR_SAGA'])
        ->and(codigoRealizacion(fn () => $this->realizar->ejecutar(realizacion(['insumos' => []]), $this->tecnico)))->toBe('CONFLICTO_IDEMPOTENCIA');
});

it('otra realización de una labor ya realizada es LABOR_NO_PROGRAMADA', function () {
    $this->realizar->ejecutar(realizacion(), $this->tecnico);

    expect(codigoRealizacion(fn () => $this->realizar->ejecutar(realizacion(['idOperacion' => 'op-3']), $this->tecnico)))->toBe('LABOR_NO_PROGRAMADA');
});

it('usar el idOperacion de la creación es CONFLICTO_IDEMPOTENCIA', function () {
    expect(codigoRealizacion(fn () => $this->realizar->ejecutar(realizacion(['idOperacion' => 'l1']), $this->tecnico)))->toBe('CONFLICTO_IDEMPOTENCIA');
});

it('vuelve a validar la campaña: finalizada → 422 y la labor sigue PROGRAMADA', function () {
    $this->pasarela->campanias['c1'] = new CampaniaConsultada('c1', 'p1', 'FINALIZADA');

    expect(codigoRealizacion(fn () => $this->realizar->ejecutar(realizacion(), $this->tecnico)))->toBe('CAMPANIA_FINALIZADA')
        ->and($this->repositorio->labores['l1']->estado)->toBe(EstadoLabor::PROGRAMADA);
});

it('con gestión caída la realización queda PENDIENTE con validación diferida', function () {
    $this->pasarela->disponible = false;

    $this->realizar->ejecutar(realizacion(['insumos' => []]), $this->tecnico);

    expect($this->repositorio->labores['l1']->estado)->toBe(EstadoLabor::PENDIENTE)
        ->and($this->repositorio->labores['l1']->validacionPendiente())->toBeTrue();
});

it('si otra realización gana la carrera, responde LABOR_NO_PROGRAMADA', function () {
    $otra = clone $this->repositorio->labores['l1'];
    $otra->realizar('op-otra', 'h', new DateTimeImmutable('2026-11-20T09:00:00Z'), new DateTimeImmutable('2026-11-20T09:00:00Z'), null, [],
        new Responsable('tec-2', 'B'), ValidacionCampania::VALIDADA, new DateTimeImmutable('2026-11-20T11:59:00Z'));
    $this->repositorio->ganadoraCarrera = $otra;

    expect(codigoRealizacion(fn () => $this->realizar->ejecutar(realizacion(), $this->tecnico)))->toBe('LABOR_NO_PROGRAMADA');
});

it('responde LABOR_NO_ENCONTRADA si no existe', function () {
    expect(codigoRealizacion(fn () => $this->realizar->ejecutar(realizacion(['idLabor' => 'nada']), $this->tecnico)))->toBe('LABOR_NO_ENCONTRADA');
});
