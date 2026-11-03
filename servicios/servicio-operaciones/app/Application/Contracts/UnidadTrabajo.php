<?php

namespace App\Application\Contracts;

/**
 * Agrupa las escrituras de una operación para confirmarlas juntas o no confirmar ninguna (README D-08).
 * Las lecturas dentro de la operación se ejecutan en el momento.
 */
interface UnidadTrabajo
{
    /**
     * @template T
     *
     * @param  callable(): T  $operacion
     * @return T
     *
     * @throws ConflictoEscritura si falla la condición de alguna escritura; no se escribe nada.
     */
    public function ejecutar(callable $operacion): mixed;
}
