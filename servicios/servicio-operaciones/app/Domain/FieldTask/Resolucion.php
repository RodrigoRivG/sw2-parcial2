<?php

namespace App\Domain\FieldTask;

use App\Domain\Shared\Motivo;
use DateTimeImmutable;

/**
 * Cómo resolvió el administrador una labor en revisión (spec-revision-labores.md RQ-REV-04).
 */
final class Resolucion
{
    public function __construct(
        public readonly DecisionRevision $decision,
        public readonly string $observacion,
        public readonly Responsable $administrador,
        public readonly DateTimeImmutable $fecha,
        public readonly ?Motivo $motivoAnterior,
    ) {}
}
