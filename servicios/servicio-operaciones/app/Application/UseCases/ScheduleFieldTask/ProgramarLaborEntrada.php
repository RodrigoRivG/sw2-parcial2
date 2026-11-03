<?php

namespace App\Application\UseCases\ScheduleFieldTask;

use App\Domain\FieldTask\TipoLabor;
use DateTimeImmutable;

final class ProgramarLaborEntrada
{
    public function __construct(
        public readonly string $idOperacion,
        public readonly DateTimeImmutable $fechaCreacion,
        public readonly TipoLabor $tipoLabor,
        public readonly string $idParcela,
        public readonly string $idCampania,
        public readonly string $fechaProgramada,
        public readonly ?string $observaciones,
    ) {}
}
