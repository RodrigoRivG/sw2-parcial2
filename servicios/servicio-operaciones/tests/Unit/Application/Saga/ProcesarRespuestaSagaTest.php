<?php

require_once __DIR__.'/../Dobles.php';

use App\Application\UseCases\Saga\AvanceSaga;
use App\Application\UseCases\Saga\EnvioComandos;
use App\Application\UseCases\Saga\ProcesarRespuestaSaga;
use App\Application\UseCases\Saga\ReanudarSagasEstancadas;
use App\Application\UseCases\Saga\RespuestaInvalida;
use App\Domain\FieldTask\ConsumoInsumo;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\Responsable;
use App\Domain\FieldTask\TipoLabor;
use App\Domain\FieldTask\ValidacionCampania;
use App\Domain\Saga\ConfiguracionSaga;
use App\Domain\Saga\EstadoSaga;
use App\Domain\Saga\Participante;
use App\Domain\Saga\PasoSaga;
use App\Domain\Saga\RespuestaSaga;
use App\Domain\Saga\Saga;
use App\Domain\Saga\TipoRespuesta;
use App\Domain\Shared\Cantidad;
use Psr\Log\NullLogger;
use Tests\Support\RelojFijo;
use Tests\Unit\Application\AuditoriaEnMemoria;
use Tests\Unit\Application\PublicadorEnMemoria;
use Tests\Unit\Application\RepositorioLaborEnMemoria;
use Tests\Unit\Application\RepositorioSagaEnMemoria;
use Tests\Unit\Application\UnidadTrabajoDirecta;

beforeEach(function () {
    $this->reloj = new RelojFijo('2026-11-02T14:00:00Z');
    $this->labores = new RepositorioLaborEnMemoria;
    $this->sagas = new RepositorioSagaEnMemoria;
    $this->publicador = new PublicadorEnMemoria;
    $this->auditoria = new AuditoriaEnMemoria;
    $this->config = new ConfiguracionSaga;

    $labor = LaborAgricola::registrarRealizada('l1', 'h', TipoLabor::RIEGO, 'p1', 'c1', $this->reloj->ahora(), $this->reloj->ahora(), null,
        [new ConsumoInsumo('i1', Cantidad::desdeTexto('2'))], new Responsable('tec', 'Ana'), ValidacionCampania::VALIDADA, $this->reloj->ahora());
    $saga = Saga::iniciar('6a1f2c3d-0000-4000-8000-000000000001', $labor, $this->reloj->ahora(), $this->config);
    $labor->iniciarSaga($saga->idSaga);
    $this->labores->labores['l1'] = $labor;
    $this->sagas->sagas[$saga->idSaga] = $saga;
    $this->idSaga = $saga->idSaga;

    $avance = new AvanceSaga($this->sagas, $this->labores, new UnidadTrabajoDirecta, $this->auditoria,
        new EnvioComandos($this->publicador, new NullLogger), $this->reloj, new NullLogger);
    $this->procesar = new ProcesarRespuestaSaga($avance, $this->config, new NullLogger);
    $this->reanudar = new ReanudarSagasEstancadas($this->sagas, $avance, $this->config, $this->reloj, new NullLogger);
});

it('aplica la respuesta, publica el comando siguiente y audita Saga y labor', function () {
    $this->procesar->ejecutar(TipoRespuesta::INSUMOS_DESCONTADOS, 'm1', $this->idSaga, ['idSaga' => $this->idSaga, 'idLabor' => 'l1', 'costoTotal' => '9.70', 'items' => []]);

    expect($this->publicador->enviados)->toHaveCount(1)
        ->and($this->publicador->enviados[0])->toMatchArray([
            'destino' => Participante::GESTION,
            'tipo' => 'RegistrarCostoCampania',
            'datos' => ['idSaga' => $this->idSaga, 'idLabor' => 'l1', 'idCampania' => 'c1', 'monto' => '9.70', 'categoria' => 'INSUMO'],
            'idCorrelacion' => $this->idSaga,
        ])
        ->and(array_column($this->auditoria->registros, 'accion'))->toBe(['AVANZAR_SAGA']);

    $this->procesar->ejecutar(TipoRespuesta::COSTO_REGISTRADO, 'm2', $this->idSaga, ['idSaga' => $this->idSaga, 'idLabor' => 'l1', 'idCampania' => 'c1', 'idCosto' => 'x', 'monto' => '9.70']);

    expect($this->labores->labores['l1']->estado)->toBe(EstadoLabor::CONFIRMADA)
        ->and($this->sagas->sagas[$this->idSaga]->estado)->toBe(EstadoSaga::COMPLETADA)
        ->and(array_column($this->auditoria->registros, 'accion'))->toBe(['AVANZAR_SAGA', 'AVANZAR_SAGA', 'ACTUALIZAR_LABOR_SAGA']);
});

it('si otra escritura gana, relee y vuelve a decidir sobre el estado nuevo', function () {
    // Mientras se procesa InsumosDescontados, otra copia del mismo mensaje ya lo aplicó
    $this->sagas->antesDeActualizar = function (RepositorioSagaEnMemoria $sagas) {
        $saga = $sagas->sagas[$this->idSaga];
        $saga->aplicarRespuesta(new RespuestaSaga(TipoRespuesta::INSUMOS_DESCONTADOS, 'm0', costoTotal: '9.70'), $this->reloj->ahora(), $this->config);
    };

    $decision = $this->procesar->ejecutar(TipoRespuesta::INSUMOS_DESCONTADOS, 'm1', $this->idSaga, ['idSaga' => $this->idSaga, 'idLabor' => 'l1', 'costoTotal' => '9.70']);

    expect($decision->tardia)->toBeTrue()
        ->and($this->publicador->enviados)->toBe([])
        ->and($this->sagas->sagas[$this->idSaga]->respuestasTardias)->toHaveCount(1);
});

it('si el broker falla, la Saga queda guardada igual y no se lanza error', function () {
    $this->publicador->falla = true;

    $this->procesar->ejecutar(TipoRespuesta::INSUMOS_DESCONTADOS, 'm1', $this->idSaga, ['idSaga' => $this->idSaga, 'idLabor' => 'l1', 'costoTotal' => '9.70']);

    expect($this->sagas->sagas[$this->idSaga]->pasoActual->value)->toBe('REGISTRAR_COSTO');
});

it('rechaza como no procesable lo que no cumple el contrato', function (TipoRespuesta $tipo, array $datos, ?string $idCorrelacion) {
    expect(fn () => $this->procesar->ejecutar($tipo, 'm1', $idCorrelacion ?? $this->idSaga, $datos + ['idSaga' => $this->idSaga, 'idLabor' => 'l1']))
        ->toThrow(RespuestaInvalida::class);
})->with([
    'costo como número' => [TipoRespuesta::INSUMOS_DESCONTADOS, ['costoTotal' => 9.7], null],
    'costo sin 2 decimales' => [TipoRespuesta::INSUMOS_DESCONTADOS, ['costoTotal' => '9.7'], null],
    'rechazo sin código' => [TipoRespuesta::COSTO_RECHAZADO, ['motivo' => 'x'], null],
    'restauración sin sinEfecto' => [TipoRespuesta::INSUMOS_RESTAURADOS, [], null],
    'idCorrelacion distinto' => [TipoRespuesta::COSTO_REGISTRADO, [], '6a1f2c3d-0000-4000-8000-0000000000ff'],
]);

it('una Saga inexistente no es procesable', function () {
    $otra = '6a1f2c3d-0000-4000-8000-000000000099';

    expect(fn () => $this->procesar->ejecutar(TipoRespuesta::COSTO_REGISTRADO, 'm1', $otra, ['idSaga' => $otra, 'idLabor' => 'l1']))
        ->toThrow(RespuestaInvalida::class);
});

it('la recuperación reenvía la Saga vencida y salta las que no vencieron', function () {
    expect($this->reanudar->ejecutar())->toBe(0);

    $this->reloj->avanzar('+31 seconds');

    expect($this->reanudar->ejecutar())->toBe(1)
        ->and($this->publicador->enviados[0]['tipo'])->toBe('DescontarInsumos')
        ->and($this->publicador->enviados[0]['datos']['items'])->toBe([['idInsumo' => 'i1', 'cantidad' => '2.000']])
        ->and($this->sagas->sagas[$this->idSaga]->paso(PasoSaga::DESCONTAR_INSUMOS)->intentos)->toBe(2);
});
