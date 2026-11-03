<?php

use App\Domain\Shared\Cantidad;
use App\Domain\Shared\ExcepcionDominio;

it('normaliza a escala 3', function (string $texto, string $esperado) {
    expect(Cantidad::desdeTexto($texto)->valor)->toBe($esperado);
})->with([
    ['100', '100.000'],
    ['2.5', '2.500'],
    ['0.001', '0.001'],
    ['999999999999.999', '999999999999.999'],
]);

it('rechaza cantidades que no son mayores a 0 o tienen más de 3 decimales', function (string $texto) {
    expect(fn () => Cantidad::desdeTexto($texto))
        ->toThrow(fn (ExcepcionDominio $e) => expect($e->codigo)->toBe('CANTIDAD_INVALIDA'));
})->with(['0', '0.000', '-1', '-0.5', '1.2345', 'abc', '', '1e3']);

it('compara sin punto flotante', function () {
    expect(Cantidad::desdeTexto('0.300')->esIgualA(Cantidad::desdeTexto('0.3')))->toBeTrue()
        ->and(Cantidad::desdeTexto('0.1')->esIgualA(Cantidad::desdeTexto('0.2')))->toBeFalse();
});
