<?php

use App\Domain\FieldTask\Responsable;
use App\Domain\Incident\ClasificacionImagen;
use App\Domain\Incident\Incidencia;
use App\Domain\Incident\OrigenClasificacion;
use App\Domain\Incident\ReferenciaFoto;
use App\Domain\Incident\TipoIncidencia;
use App\Domain\Shared\ExcepcionDominio;

function incidenciaEn(string $observacion, string $creacion = '2026-11-02T13:59:00Z', string $registrador = 'tec'): Incidencia
{
    $utc = new DateTimeZone('UTC');

    return Incidencia::registrar('i1', 'h', TipoIncidencia::PLAGA, '  Pulgón  ', new DateTimeImmutable($observacion, $utc),
        new DateTimeImmutable($creacion, $utc), 'p1', null, new ReferenciaFoto('k', 'image/jpeg', 1), null,
        new Responsable($registrador, 'Ana'), new DateTimeImmutable('2026-11-02T14:00:00Z', $utc));
}

it('se registra con la descripción recortada y la notificación pendiente', function () {
    $incidencia = incidenciaEn('2026-11-02T13:00:00Z');

    expect($incidencia->descripcion)->toBe('Pulgón')
        ->and($incidencia->notificacionPendiente)->toBeTrue()
        ->and($incidencia->fechaRecepcion)->toEqual(new DateTimeImmutable('2026-11-02T14:00:00Z'));
});

it('admite hasta 5 minutos de adelanto del reloj del dispositivo y rechaza más', function () {
    expect(incidenciaEn('2026-11-02T14:05:00Z')->id)->toBe('i1')
        ->and(fn () => incidenciaEn('2026-11-02T14:05:01Z'))->toThrow(ExcepcionDominio::class, 'futuro')
        ->and(fn () => incidenciaEn('2026-11-02T13:00:00Z', creacion: '2026-11-02T14:06:00Z'))->toThrow(ExcepcionDominio::class);
});

it('valida la confianza entre 0 y 1 y la normaliza a 4 decimales', function (string $confianza, ?string $esperado) {
    $crear = fn () => ClasificacionImagen::crear(' roya ', $confianza, 'v1', OrigenClasificacion::DISPOSITIVO);

    if ($esperado === null) {
        expect($crear)->toThrow(fn (ExcepcionDominio $e) => expect($e->codigo)->toBe('CONFIANZA_INVALIDA'));
    } else {
        expect($crear()->confianza)->toBe($esperado)->and($crear()->categoria)->toBe('roya');
    }
})->with([
    ['0', '0.0000'], ['1', '1.0000'], ['0.8731', '0.8731'], ['1.0001', null], ['-0.1', null], ['abc', null],
]);

it('la ven administración, gerencia y lectura; el técnico solo las suyas', function () {
    $incidencia = incidenciaEn('2026-11-02T13:00:00Z', registrador: 'tec-1');

    expect($incidencia->puedeVerla('x', ['gerencia']))->toBeTrue()
        ->and($incidencia->puedeVerla('x', ['lectura_operaciones']))->toBeTrue()
        ->and($incidencia->puedeVerla('tec-1', ['tecnico_campo']))->toBeTrue()
        ->and($incidencia->puedeVerla('tec-2', ['tecnico_campo']))->toBeFalse()
        ->and(Incidencia::veTodas(['tecnico_campo']))->toBeFalse();
});
