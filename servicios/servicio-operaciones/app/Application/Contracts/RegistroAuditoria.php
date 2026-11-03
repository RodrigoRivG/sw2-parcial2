<?php

namespace App\Application\Contracts;

/**
 * Registra quién hizo qué sobre qué entidad, en la misma unidad de trabajo del cambio (README D-09).
 */
interface RegistroAuditoria
{
    public function registrar(string $actor, string $accion, string $entidad, string $idEntidad): void;
}
