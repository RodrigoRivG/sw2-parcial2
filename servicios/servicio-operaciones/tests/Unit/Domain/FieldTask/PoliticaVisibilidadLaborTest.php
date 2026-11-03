<?php

use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\PoliticaVisibilidadLabor;
use App\Domain\FieldTask\Responsable;
use App\Domain\FieldTask\TipoLabor;
use App\Domain\FieldTask\ValidacionCampania;

function laborDe(string $responsable, bool $programada): LaborAgricola
{
    $utc = new DateTimeZone('UTC');
    $ahora = new DateTimeImmutable('2026-11-02T14:00:00Z', $utc);

    return $programada
        ? LaborAgricola::programar('l', 'h', TipoLabor::RIEGO, 'p', 'c', '2026-11-10', $ahora, null, new Responsable($responsable, 'X'), ValidacionCampania::VALIDADA, $ahora)
        : LaborAgricola::registrarRealizada('l', 'h', TipoLabor::RIEGO, 'p', 'c', $ahora, $ahora, null, [], new Responsable($responsable, 'X'), ValidacionCampania::VALIDADA, $ahora);
}

it('administrador, gerencia y lectura_operaciones ven todas', function (string $rol) {
    expect(PoliticaVisibilidadLabor::puedeVer(laborDe('otro', false), 'yo', [$rol]))->toBeTrue()
        ->and(PoliticaVisibilidadLabor::veTodas([$rol]))->toBeTrue();
})->with(['administrador', 'gerencia', 'lectura_operaciones']);

it('el técnico ve las programadas y las suyas, no las realizadas ajenas', function () {
    expect(PoliticaVisibilidadLabor::puedeVer(laborDe('otro', true), 'yo', ['tecnico_campo']))->toBeTrue()
        ->and(PoliticaVisibilidadLabor::puedeVer(laborDe('yo', false), 'yo', ['tecnico_campo']))->toBeTrue()
        ->and(PoliticaVisibilidadLabor::puedeVer(laborDe('otro', false), 'yo', ['tecnico_campo']))->toBeFalse()
        ->and(PoliticaVisibilidadLabor::veTodas(['tecnico_campo']))->toBeFalse();
});

it('con técnico y gerencia a la vez ve todas', function () {
    expect(PoliticaVisibilidadLabor::puedeVer(laborDe('otro', false), 'yo', ['tecnico_campo', 'gerencia']))->toBeTrue();
});

it('sin roles conocidos no ve nada', function () {
    expect(PoliticaVisibilidadLabor::puedeVer(laborDe('yo', true), 'yo', ['offline_access']))->toBeFalse();
});
