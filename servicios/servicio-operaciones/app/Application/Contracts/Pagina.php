<?php

namespace App\Application\Contracts;

/**
 * Página de un listado por cursor (README D-05).
 *
 * @template T
 */
final class Pagina
{
    /**
     * @param  list<T>  $items
     */
    public function __construct(
        public readonly array $items,
        public readonly ?string $siguienteCursor,
    ) {}
}
