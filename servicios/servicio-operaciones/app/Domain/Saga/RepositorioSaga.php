<?php

namespace App\Domain\Saga;

use DateTimeImmutable;

interface RepositorioSaga
{
    public function buscar(string $idSaga): ?Saga;

    public function guardarNueva(Saga $saga): void;

    /** Escritura condicional a la versión leída (README D-07). */
    public function actualizar(Saga $saga, int $versionLeida): void;

    /**
     * Sagas activas cuya fecha límite ya venció (RQ-SAG-09). El índice es eventual: el caso de uso relee cada una.
     *
     * @return list<string> identificadores
     */
    public function vencidas(DateTimeImmutable $ahora, int $maximo): array;
}
