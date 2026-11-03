<?php

namespace App\Application\UseCases\SyncOfflineOperations;

use App\Application\UseCases\RegisterFieldTask\RealizarLaborEntrada;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborEntrada;
use App\Application\UseCases\RegisterIncident\RegistrarIncidenciaEntrada;
use App\Application\UseCases\ScheduleFieldTask\ProgramarLaborEntrada;
use App\Domain\Shared\Motivo;
use DateTimeImmutable;

/**
 * Una operación del lote ya leída por el adaptador: o trae la entrada de su caso de uso, o el motivo por el que no
 * se puede procesar. Sin `tipo`, `idOperacion` o `fechaCreacion` válidos el sobre no sirve y va al final (RQ-SIN-03).
 */
final class OperacionSincronizacion
{
    public function __construct(
        public readonly int $indice,
        public readonly ?string $tipo,
        public readonly ?string $idOperacion,
        public readonly ?DateTimeImmutable $fechaCreacion,
        public readonly ProgramarLaborEntrada|RegistrarLaborEntrada|RealizarLaborEntrada|RegistrarIncidenciaEntrada|null $entrada,
        public readonly ?Motivo $error = null,
    ) {}

    public function sobreValido(): bool
    {
        return $this->tipo !== null && $this->idOperacion !== null && $this->fechaCreacion !== null;
    }
}
