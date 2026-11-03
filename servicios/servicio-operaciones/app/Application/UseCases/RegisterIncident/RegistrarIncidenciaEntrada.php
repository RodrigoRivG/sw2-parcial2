<?php

namespace App\Application\UseCases\RegisterIncident;

use App\Domain\Incident\OrigenClasificacion;
use App\Domain\Incident\TipoIncidencia;
use DateTimeImmutable;

final class RegistrarIncidenciaEntrada
{
    /**
     * @param  array{categoria: string, confianza: string, versionModelo: string, origen: OrigenClasificacion}|null  $clasificacion
     */
    public function __construct(
        public readonly string $idOperacion,
        public readonly DateTimeImmutable $fechaCreacion,
        public readonly TipoIncidencia $tipo,
        public readonly string $descripcion,
        public readonly DateTimeImmutable $fechaObservacion,
        public readonly string $idParcela,
        public readonly ?string $idCampania,
        public readonly ?array $clasificacion,
        public readonly string $contenidoFoto,
        public readonly string $idCorrelacion,
    ) {}
}
