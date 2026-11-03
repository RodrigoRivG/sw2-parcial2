<?php

namespace App\Domain\Saga;

/**
 * Tiempos y reintentos de la Saga (RQ-SAG-06).
 */
final class ConfiguracionSaga
{
    public function __construct(
        public readonly int $tiempoLimiteSegundos = 30,
        public readonly int $maximoEnvios = 4,
        public readonly int $esperaMaximaCompensacionSegundos = 600,
    ) {}
}
