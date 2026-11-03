<?php

namespace App\Application\UseCases\ResolveReview;

use App\Domain\FieldTask\DecisionRevision;

final class ResolverRevisionEntrada
{
    public function __construct(
        public readonly string $idLabor,
        public readonly DecisionRevision $decision,
        public readonly string $observacion,
        public readonly int $version,
    ) {}
}
