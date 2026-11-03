<?php

namespace App\Domain\Shared;

use RuntimeException;

/**
 * Error de negocio con código estable. El dominio no conoce HTTP: el adaptador traduce el tipo a un estado.
 */
class ExcepcionDominio extends RuntimeException
{
    /**
     * @param  list<array<string, mixed>>  $detalles
     */
    public function __construct(
        public readonly string $codigo,
        string $mensaje,
        public readonly TipoErrorDominio $tipo,
        public readonly array $detalles = [],
    ) {
        parent::__construct($mensaje);
    }

    public static function noEncontrado(string $codigo, string $mensaje): self
    {
        return new self($codigo, $mensaje, TipoErrorDominio::NO_ENCONTRADO);
    }

    /**
     * @param  list<array<string, mixed>>  $detalles
     */
    public static function conflicto(string $codigo, string $mensaje, array $detalles = []): self
    {
        return new self($codigo, $mensaje, TipoErrorDominio::CONFLICTO, $detalles);
    }

    /**
     * @param  list<array<string, mixed>>  $detalles
     */
    public static function reglaNegocio(string $codigo, string $mensaje, array $detalles = []): self
    {
        return new self($codigo, $mensaje, TipoErrorDominio::REGLA_NEGOCIO, $detalles);
    }
}
