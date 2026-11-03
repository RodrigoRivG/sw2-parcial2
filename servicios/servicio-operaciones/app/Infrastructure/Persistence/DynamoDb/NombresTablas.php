<?php

namespace App\Infrastructure\Persistence\DynamoDb;

/**
 * Nombre real de cada tabla: el prefijo solo se usa en los tests (README D-17).
 */
final class NombresTablas
{
    public function __construct(private readonly string $prefijo) {}

    public function de(string $tabla): string
    {
        return $this->prefijo.$tabla;
    }

    public function prefijo(): string
    {
        return $this->prefijo;
    }
}
