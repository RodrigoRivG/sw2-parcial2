<?php

namespace App\Domain\FieldTask;

/**
 * Usuario de Keycloak (`sub`) con una copia de su nombre; nunca texto libre (constitución §3).
 */
final class Responsable
{
    public function __construct(
        public readonly string $id,
        public readonly string $nombre,
    ) {}
}
