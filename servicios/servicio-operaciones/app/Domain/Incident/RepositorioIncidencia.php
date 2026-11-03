<?php

namespace App\Domain\Incident;

use DateTimeImmutable;

interface RepositorioIncidencia
{
    public function buscar(string $id): ?Incidencia;

    /** Escritura condicional `attribute_not_exists(id)`; en una unidad de trabajo, se agrega a la transacción. */
    public function guardarNueva(Incidencia $incidencia): void;

    /** El broker confirmó el evento: la incidencia deja de estar pendiente de notificar (RQ-INC-08). */
    public function marcarNotificada(string $id): void;

    /**
     * Incidencias cuyo evento no se confirmó y que se recibieron antes de `$antesDe`.
     *
     * @return list<Incidencia>
     */
    public function pendientesDeNotificar(DateTimeImmutable $antesDe, int $maximo): array;
}
