<?php

namespace App\Application\Contracts;

use RuntimeException;

/**
 * Una escritura condicional no se cumplió (el ítem ya existía o cambió desde que se leyó).
 * `etiqueta` identifica la escritura que falló, para que el caso de uso decida qué hacer.
 */
final class ConflictoEscritura extends RuntimeException
{
    public function __construct(public readonly string $etiqueta)
    {
        parent::__construct("Falló la condición de la escritura '{$etiqueta}'.");
    }
}
