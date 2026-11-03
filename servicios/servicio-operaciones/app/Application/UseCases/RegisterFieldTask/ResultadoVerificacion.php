<?php

namespace App\Application\UseCases\RegisterFieldTask;

use App\Domain\Shared\Motivo;

/**
 * Resultado de consultar la campaña (spec-labores.md RQ-LAB-05): válida, rechazada con su motivo o no disponible.
 */
final class ResultadoVerificacion
{
    private function __construct(
        public readonly bool $disponible,
        public readonly ?Motivo $rechazo,
    ) {}

    public static function valida(): self
    {
        return new self(true, null);
    }

    public static function rechazada(Motivo $motivo): self
    {
        return new self(true, $motivo);
    }

    public static function noDisponible(): self
    {
        return new self(false, null);
    }
}
