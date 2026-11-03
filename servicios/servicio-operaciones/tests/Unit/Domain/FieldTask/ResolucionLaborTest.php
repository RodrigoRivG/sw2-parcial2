<?php

use App\Domain\FieldTask\ConsumoInsumo;
use App\Domain\FieldTask\DecisionRevision;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\Responsable;
use App\Domain\FieldTask\TipoLabor;
use App\Domain\FieldTask\ValidacionCampania;
use App\Domain\Saga\EstadoSaga;
use App\Domain\Shared\Cantidad;
use App\Domain\Shared\ExcepcionDominio;
use App\Domain\Shared\Motivo;

function laborEnRevision(): LaborAgricola
{
    $ahora = new DateTimeImmutable('2026-11-02T14:00:00Z');
    $labor = LaborAgricola::registrarRealizada('l1', 'h', TipoLabor::RIEGO, 'p1', 'c1', $ahora, $ahora, null,
        [new ConsumoInsumo('i1', Cantidad::desdeTexto('1'))], new Responsable('tec', 'Ana'), ValidacionCampania::VALIDADA, $ahora);
    $labor->iniciarSaga('s1');
    $labor->registrarResultadoSaga(EstadoLabor::PENDIENTE_REVISION, new Motivo('SIN_RESPUESTA_GESTION', 'Gestión no respondió.'), $ahora);

    return $labor;
}

function resolverCon(LaborAgricola $labor, DecisionRevision $decision, EstadoSaga $saga): string
{
    try {
        $labor->resolver($decision, '  Gestión estuvo caída  ', new Responsable('adm', 'Luis'), $saga, new DateTimeImmutable('2026-11-02T16:00:00Z'));
    } catch (ExcepcionDominio $e) {
        return $e->codigo;
    }

    return $labor->estado->value;
}

it('aplica cada fila de RQ-REV-02', function (EstadoSaga $saga, DecisionRevision $decision, string $esperado) {
    expect(resolverCon(laborEnRevision(), $decision, $saga))->toBe($esperado);
})->with(function () {
    $esperados = [
        'COMPENSADA' => ['CONFIRMAR' => 'DECISION_NO_PERMITIDA', 'RECHAZAR' => 'RECHAZADA', 'REINTENTAR' => 'PENDIENTE'],
        'REQUIERE_INTERVENCION' => ['CONFIRMAR' => 'CONFIRMADA', 'RECHAZAR' => 'DECISION_NO_PERMITIDA', 'REINTENTAR' => 'DECISION_NO_PERMITIDA'],
        'EN_CURSO' => ['CONFIRMAR' => 'SAGA_EN_CURSO', 'RECHAZAR' => 'SAGA_EN_CURSO', 'REINTENTAR' => 'SAGA_EN_CURSO'],
        'COMPENSANDO' => ['CONFIRMAR' => 'SAGA_EN_CURSO', 'RECHAZAR' => 'SAGA_EN_CURSO', 'REINTENTAR' => 'SAGA_EN_CURSO'],
        'COMPLETADA' => ['CONFIRMAR' => 'DECISION_NO_PERMITIDA', 'RECHAZAR' => 'DECISION_NO_PERMITIDA', 'REINTENTAR' => 'DECISION_NO_PERMITIDA'],
        'RECHAZADA' => ['CONFIRMAR' => 'DECISION_NO_PERMITIDA', 'RECHAZAR' => 'DECISION_NO_PERMITIDA', 'REINTENTAR' => 'DECISION_NO_PERMITIDA'],
    ];
    foreach ($esperados as $saga => $porDecision) {
        foreach ($porDecision as $decision => $esperado) {
            yield "{$saga} + {$decision}" => [EstadoSaga::from($saga), DecisionRevision::from($decision), $esperado];
        }
    }
});

it('RECHAZAR deja el motivo RECHAZADA_EN_REVISION y guarda la resolución con el motivo anterior', function () {
    $labor = laborEnRevision();
    resolverCon($labor, DecisionRevision::RECHAZAR, EstadoSaga::COMPENSADA);

    expect($labor->motivo?->codigo)->toBe('RECHAZADA_EN_REVISION')
        ->and($labor->resolucion?->decision)->toBe(DecisionRevision::RECHAZAR)
        ->and($labor->resolucion?->observacion)->toBe('Gestión estuvo caída')
        ->and($labor->resolucion?->administrador->id)->toBe('adm')
        ->and($labor->resolucion?->motivoAnterior?->codigo)->toBe('SIN_RESPUESTA_GESTION')
        ->and($labor->version)->toBe(2);
});

it('REINTENTAR deja la labor lista para una Saga nueva y guarda la anterior', function () {
    $labor = laborEnRevision();
    resolverCon($labor, DecisionRevision::REINTENTAR, EstadoSaga::COMPENSADA);

    expect($labor->idSaga)->toBeNull()
        ->and($labor->idsSagaAnteriores)->toBe(['s1'])
        ->and($labor->motivo)->toBeNull()
        ->and($labor->requiereSaga())->toBeTrue();
});

it('CONFIRMAR quita el motivo', function () {
    $labor = laborEnRevision();
    resolverCon($labor, DecisionRevision::CONFIRMAR, EstadoSaga::REQUIERE_INTERVENCION);

    expect($labor->motivo)->toBeNull()->and($labor->resolucion?->motivoAnterior?->codigo)->toBe('SIN_RESPUESTA_GESTION');
});

it('informa las decisiones permitidas en los detalles', function () {
    try {
        laborEnRevision()->resolver(DecisionRevision::CONFIRMAR, 'x', new Responsable('a', 'A'), EstadoSaga::COMPENSADA, new DateTimeImmutable);
    } catch (ExcepcionDominio $e) {
        expect($e->detalles)->toBe([['decisionesPermitidas' => ['RECHAZAR', 'REINTENTAR']]]);

        return;
    }
    $this->fail('Debía rechazar la decisión.');
});

it('una labor que no está en revisión no se resuelve', function () {
    $labor = laborEnRevision();
    resolverCon($labor, DecisionRevision::RECHAZAR, EstadoSaga::COMPENSADA);

    expect(resolverCon($labor, DecisionRevision::RECHAZAR, EstadoSaga::COMPENSADA))->toBe('LABOR_NO_EN_REVISION');
});
