<?php

namespace App\Domain\FieldTask;

use App\Domain\Shared\Cantidad;

final class ConsumoInsumo
{
    public function __construct(
        public readonly string $idInsumo,
        public readonly Cantidad $cantidad,
    ) {}
}
