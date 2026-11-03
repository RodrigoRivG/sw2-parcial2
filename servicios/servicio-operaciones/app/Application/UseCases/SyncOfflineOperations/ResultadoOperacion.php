<?php

namespace App\Application\UseCases\SyncOfflineOperations;

use App\Domain\Shared\ResultadoSincronizacion;

/**
 * Resultado de una operación del lote (spec-sincronizacion.md RQ-SIN-06).
 */
final class ResultadoOperacion
{
    /**
     * @param  list<array<string, mixed>>  $detalles
     */
    private function __construct(
        public readonly ?string $idOperacion,
        public readonly ?string $tipo,
        public readonly ResultadoSincronizacion $resultado,
        public readonly bool $repetida = false,
        public readonly ?string $idRecurso = null,
        public readonly ?string $estado = null,
        public readonly ?string $codigo = null,
        public readonly ?string $mensaje = null,
        public readonly array $detalles = [],
        public readonly bool $reintentable = false,
    ) {}

    public static function sincronizada(OperacionSincronizacion $operacion, bool $repetida, string $idRecurso, ?string $estado): self
    {
        return new self($operacion->idOperacion, $operacion->tipo, ResultadoSincronizacion::SINCRONIZADA, $repetida, $idRecurso, $estado);
    }

    /**
     * @param  list<array<string, mixed>>  $detalles
     */
    public static function error(OperacionSincronizacion $operacion, string $codigo, string $mensaje, array $detalles = [], bool $reintentable = false): self
    {
        return new self($operacion->idOperacion, $operacion->tipo, ResultadoSincronizacion::ERROR,
            codigo: $codigo, mensaje: $mensaje, detalles: $detalles, reintentable: $reintentable);
    }
}
