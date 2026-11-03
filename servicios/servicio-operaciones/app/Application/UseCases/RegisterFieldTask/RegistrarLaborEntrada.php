<?php

namespace App\Application\UseCases\RegisterFieldTask;

use App\Domain\FieldTask\TipoLabor;
use DateTimeImmutable;

final class RegistrarLaborEntrada
{
    /**
     * @param  list<array{idInsumo: string, cantidad: string}>  $insumos
     */
    public function __construct(
        public readonly string $idOperacion,
        public readonly DateTimeImmutable $fechaCreacion,
        public readonly TipoLabor $tipoLabor,
        public readonly string $idParcela,
        public readonly string $idCampania,
        public readonly DateTimeImmutable $fechaEjecucion,
        public readonly ?string $observaciones,
        public readonly array $insumos,
    ) {}
}
