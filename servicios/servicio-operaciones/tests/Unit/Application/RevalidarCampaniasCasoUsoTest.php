<?php

require_once __DIR__.'/Dobles.php';

use App\Application\UseCases\RegisterFieldTask\VerificadorCampania;
use App\Application\UseCases\RevalidateCampaign\RevalidarCampaniasCasoUso;
use App\Domain\FieldTask\CampaniaConsultada;
use App\Domain\FieldTask\ConsumoInsumo;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\Responsable;
use App\Domain\FieldTask\TipoLabor;
use App\Domain\FieldTask\ValidacionCampania;
use App\Domain\Shared\Cantidad;
use Psr\Log\NullLogger;
use Tests\Support\RelojFijo;
use Tests\Unit\Application\AuditoriaEnMemoria;
use Tests\Unit\Application\PasarelaCampaniaFalsa;
use Tests\Unit\Application\RepositorioLaborEnMemoria;
use Tests\Unit\Application\UnidadTrabajoDirecta;

use function Tests\Unit\Application\iniciarSagaEnMemoria;

beforeEach(function () {
    $this->reloj = new RelojFijo('2026-11-02T14:00:00Z');
    $this->repositorio = new RepositorioLaborEnMemoria;
    $this->auditoria = new AuditoriaEnMemoria;
    $this->pasarela = new PasarelaCampaniaFalsa;
    $this->revalidar = new RevalidarCampaniasCasoUso($this->repositorio, new UnidadTrabajoDirecta, $this->auditoria,
        new VerificadorCampania($this->pasarela, new NullLogger), $this->reloj, iniciarSagaEnMemoria($this->auditoria));
});

function laborDiferida(string $id, string $idCampania, bool $conInsumos = false): LaborAgricola
{
    $ahora = new DateTimeImmutable('2026-11-02T14:00:00Z');

    return LaborAgricola::registrarRealizada($id, 'h', TipoLabor::RIEGO, 'p1', $idCampania, $ahora, $ahora, null,
        $conInsumos ? [new ConsumoInsumo('i1', Cantidad::desdeTexto('1'))] : [], new Responsable('tec', 'Ana'),
        ValidacionCampania::PENDIENTE, $ahora);
}

it('no toca las labores cuyo próximo intento todavía no vence', function () {
    $this->repositorio->labores['l1'] = laborDiferida('l1', 'c1');

    expect($this->revalidar->ejecutar())->toBe(['validadas' => 0, 'rechazadas' => 0, 'pospuestas' => 0])
        ->and($this->pasarela->consultas)->toBe(0);
});

it('valida, rechaza o pospone según la respuesta de gestión', function () {
    $this->repositorio->labores['l1'] = laborDiferida('l1', 'c-ok');
    $this->repositorio->labores['l2'] = laborDiferida('l2', 'c-fin', conInsumos: true);
    $this->repositorio->labores['l3'] = laborDiferida('l3', 'c-nada');
    $this->pasarela->campanias['c-ok'] = new CampaniaConsultada('c-ok', 'p1', 'EN_CURSO');
    $this->pasarela->campanias['c-fin'] = new CampaniaConsultada('c-fin', 'p1', 'FINALIZADA');
    $this->reloj->avanzar('+1 minute');

    expect($this->revalidar->ejecutar())->toBe(['validadas' => 1, 'rechazadas' => 2, 'pospuestas' => 0])
        ->and($this->repositorio->labores['l1']->estado)->toBe(EstadoLabor::CONFIRMADA)
        ->and($this->repositorio->labores['l2']->estado)->toBe(EstadoLabor::RECHAZADA)
        ->and($this->repositorio->labores['l2']->motivo?->codigo)->toBe('CAMPANIA_FINALIZADA')
        ->and($this->repositorio->labores['l3']->motivo?->codigo)->toBe('CAMPANIA_NO_ENCONTRADA')
        ->and(array_column($this->auditoria->registros, 'accion'))->toBe(['VALIDAR_CAMPANIA', 'VALIDAR_CAMPANIA', 'VALIDAR_CAMPANIA'])
        ->and($this->auditoria->registros[0]['actor'])->toBe('servicio-operaciones');
});

it('con gestión caída pospone con espera creciente y sin auditar', function () {
    $this->repositorio->labores['l1'] = laborDiferida('l1', 'c1');
    $this->pasarela->disponible = false;
    $this->reloj->avanzar('+1 minute');

    $this->revalidar->ejecutar();
    $primera = $this->repositorio->labores['l1']->fechaProximoValidacion;
    $this->reloj->avanzar('+2 minutes');
    $this->revalidar->ejecutar();

    expect($primera)->toEqual(new DateTimeImmutable('2026-11-02T14:03:00Z'))
        ->and($this->repositorio->labores['l1']->fechaProximoValidacion)->toEqual(new DateTimeImmutable('2026-11-02T14:07:00Z'))
        ->and($this->repositorio->labores['l1']->estado)->toBe(EstadoLabor::PENDIENTE)
        ->and($this->auditoria->registros)->toBe([]);
});

it('si otra ejecución ya procesó la labor, la salta sin error', function () {
    $diferida = laborDiferida('l1', 'c1');
    $this->repositorio->labores['l1'] = $diferida;
    $this->pasarela->campanias['c1'] = new CampaniaConsultada('c1', 'p1', 'EN_CURSO');
    $ganadora = clone $diferida;
    $ganadora->aplicarValidacion(null, new DateTimeImmutable('2026-11-02T14:00:30Z'));
    $this->repositorio->ganadoraCarrera = $ganadora;
    $this->reloj->avanzar('+1 minute');

    expect($this->revalidar->ejecutar())->toBe(['validadas' => 0, 'rechazadas' => 0, 'pospuestas' => 0])
        ->and($this->auditoria->registros)->toBe([]);
});
