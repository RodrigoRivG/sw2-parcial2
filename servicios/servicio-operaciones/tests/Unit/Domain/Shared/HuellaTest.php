<?php

use App\Domain\Shared\Huella;

it('da la misma huella con otro orden de campos y otros espacios', function () {
    $a = Huella::calcular(['tipoLabor' => 'RIEGO', 'observaciones' => 'Riego por goteo', 'idParcela' => 'p1'], 'u1');
    $b = Huella::calcular(['idParcela' => 'p1', 'observaciones' => '  Riego por goteo ', 'tipoLabor' => 'RIEGO'], 'u1');

    expect($a)->toBe($b)->toHaveLength(64);
});

it('cambia con otro contenido o con otro usuario', function () {
    $base = Huella::calcular(['cantidad' => '100.000'], 'u1');

    expect(Huella::calcular(['cantidad' => '100.500'], 'u1'))->not->toBe($base)
        ->and(Huella::calcular(['cantidad' => '100.000'], 'u2'))->not->toBe($base);
});

it('respeta el orden de las listas', function () {
    expect(Huella::calcular(['l' => ['a', 'b']], 'u'))->not->toBe(Huella::calcular(['l' => ['b', 'a']], 'u'));
});
