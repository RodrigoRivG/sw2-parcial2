<?php

namespace App\Domain\FieldTask;

use DateTimeImmutable;

interface RepositorioLabor
{
    /** Lectura consistente: la usa la idempotencia para ver lo que otra solicitud acaba de escribir. */
    public function buscar(string $id): ?LaborAgricola;

    /** Escritura condicional `attribute_not_exists(id)`; en una unidad de trabajo, se agrega a la transacción. */
    public function guardarNueva(LaborAgricola $labor): void;

    /**
     * Escritura condicional a la versión leída (y, si se indica, al estado esperado) (README D-07).
     */
    public function actualizar(LaborAgricola $labor, int $versionLeida, ?EstadoLabor $estadoEsperado = null): void;

    /**
     * Labores con la validación de campaña diferida cuyo próximo intento ya venció (RQ-LAB-10).
     *
     * @return list<LaborAgricola>
     */
    public function conValidacionVencida(DateTimeImmutable $ahora, int $maximo): array;
}
