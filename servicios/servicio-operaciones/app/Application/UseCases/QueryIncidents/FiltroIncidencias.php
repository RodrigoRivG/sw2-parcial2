<?php

namespace App\Application\UseCases\QueryIncidents;

use App\Domain\Incident\TipoIncidencia;

/**
 * Filtros del listado (spec-incidencias.md RQ-INC-09). Fechas sin hora, días completos en UTC.
 */
final class FiltroIncidencias
{
    public function __construct(
        public readonly ?string $idParcela = null,
        public readonly ?string $idCampania = null,
        public readonly ?string $idRegistrador = null,
        public readonly ?TipoIncidencia $tipo = null,
        public readonly ?string $fechaDesde = null,
        public readonly ?string $fechaHasta = null,
        public readonly bool $ascendente = false,
        public readonly int $limite = 20,
        public readonly ?string $cursor = null,
    ) {}

    public function conRegistrador(string $idRegistrador): self
    {
        return new self($this->idParcela, $this->idCampania, $idRegistrador, $this->tipo, $this->fechaDesde, $this->fechaHasta,
            $this->ascendente, $this->limite, $this->cursor);
    }
}
