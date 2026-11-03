<?php

namespace App\Infrastructure\Persistence\DynamoDb;

use DateTimeImmutable;
use DateTimeZone;

/**
 * Fechas como texto ISO 8601 UTC, que ordena bien en los índices (README D-04).
 */
final class FormatoFecha
{
    public static function conHora(DateTimeImmutable $fecha): string
    {
        return $fecha->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:s\Z');
    }

    public static function leerConHora(string $texto): DateTimeImmutable
    {
        return new DateTimeImmutable($texto, new DateTimeZone('UTC'));
    }
}
