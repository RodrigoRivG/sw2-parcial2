<?php

namespace Tests\Support;

use DateTimeImmutable;
use DateTimeZone;
use Illuminate\Support\Str;

/**
 * Cuerpos de solicitud de labores para los tests de integración (spec-labores.md 2.2).
 */
final class DatosLabor
{
    public static function uuid(): string
    {
        return (string) Str::uuid();
    }

    /** Fecha y hora UTC relativa a ahora (o a la fecha base indicada). */
    public static function fecha(string $intervalo = 'now', ?string $base = null): string
    {
        return (new DateTimeImmutable($base ?? 'now', new DateTimeZone('UTC')))->modify($intervalo)->format('Y-m-d\TH:i:s\Z');
    }

    /**
     * @param  array<string, mixed>  $cambios
     * @return array<string, mixed>
     */
    public static function realizada(string $idParcela, string $idCampania, array $cambios = []): array
    {
        return array_merge([
            'idOperacion' => self::uuid(),
            'fechaCreacion' => self::fecha('-1 minute'),
            'tipoLabor' => 'RIEGO',
            'idParcela' => $idParcela,
            'idCampania' => $idCampania,
            'fechaEjecucion' => self::fecha('-30 minutes'),
        ], $cambios);
    }

    /**
     * @param  array<string, mixed>  $cambios
     * @return array<string, mixed>
     */
    public static function programada(string $idParcela, string $idCampania, array $cambios = []): array
    {
        return array_merge([
            'idOperacion' => self::uuid(),
            'fechaCreacion' => self::fecha('-1 minute'),
            'tipoLabor' => 'FERTILIZACION',
            'idParcela' => $idParcela,
            'idCampania' => $idCampania,
            'fechaProgramada' => (new DateTimeImmutable('+18 days', new DateTimeZone('UTC')))->format('Y-m-d'),
        ], $cambios);
    }

    /**
     * @param  array<string, mixed>  $cambios
     * @return array<string, mixed>
     */
    public static function realizacion(array $cambios = []): array
    {
        return array_merge([
            'idOperacion' => self::uuid(),
            'fechaCreacion' => self::fecha('-1 minute'),
            'fechaEjecucion' => self::fecha('-10 minutes'),
        ], $cambios);
    }

    /**
     * @return list<array{idInsumo: string, cantidad: string}>
     */
    public static function insumos(string ...$cantidades): array
    {
        return array_map(fn (string $cantidad) => ['idInsumo' => self::uuid(), 'cantidad' => $cantidad], $cantidades);
    }
}
