<?php

namespace App\Application\UseCases\RegisterFieldTask;

use App\Domain\FieldTask\LaborAgricola;

/**
 * La labor y si la operación ya estaba procesada (repetida → 200 en lugar de 201).
 */
final class ResultadoLabor
{
    public function __construct(
        public readonly LaborAgricola $labor,
        public readonly bool $repetida,
    ) {}
}
