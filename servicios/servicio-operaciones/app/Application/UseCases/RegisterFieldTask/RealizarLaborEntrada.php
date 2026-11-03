<?php

namespace App\Application\UseCases\RegisterFieldTask;

use DateTimeImmutable;

final class RealizarLaborEntrada
{
    /**
     * @param  list<array{idInsumo: string, cantidad: string}>  $insumos
     */
    public function __construct(
        public readonly string $idLabor,
        public readonly string $idOperacion,
        public readonly DateTimeImmutable $fechaCreacion,
        public readonly DateTimeImmutable $fechaEjecucion,
        public readonly ?string $observaciones,
        public readonly array $insumos,
    ) {}
}
