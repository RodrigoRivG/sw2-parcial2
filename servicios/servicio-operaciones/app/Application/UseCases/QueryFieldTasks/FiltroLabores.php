<?php

namespace App\Application\UseCases\QueryFieldTasks;

use App\Domain\FieldTask\EstadoLabor;

/**
 * Filtros del listado (spec-labores.md RQ-LAB-14). Fechas sin hora, días completos en UTC.
 */
final class FiltroLabores
{
    public function __construct(
        public readonly ?string $idCampania = null,
        public readonly ?string $idResponsable = null,
        public readonly ?EstadoLabor $estado = null,
        public readonly ?string $fechaDesde = null,
        public readonly ?string $fechaHasta = null,
        public readonly bool $ascendente = false,
        public readonly int $limite = 20,
        public readonly ?string $cursor = null,
    ) {}

    public function conResponsable(string $idResponsable): self
    {
        return new self(
            $this->idCampania, $idResponsable, $this->estado, $this->fechaDesde, $this->fechaHasta,
            $this->ascendente, $this->limite, $this->cursor,
        );
    }
}
