<?php

namespace App\Domain\Shared;

/**
 * Por qué una operación se rechazó o quedó en revisión. Queda guardado en la labor (RNF-14).
 */
final class Motivo
{
    /**
     * @param  list<array<string, mixed>>  $detalles
     */
    public function __construct(
        public readonly string $codigo,
        public readonly string $mensaje,
        public readonly array $detalles = [],
    ) {}

    public function comoRegla(): ExcepcionDominio
    {
        return ExcepcionDominio::reglaNegocio($this->codigo, $this->mensaje, $this->detalles);
    }
}
