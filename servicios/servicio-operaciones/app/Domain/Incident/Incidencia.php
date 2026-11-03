<?php

namespace App\Domain\Incident;

use App\Domain\FieldTask\Responsable;
use App\Domain\Shared\ExcepcionDominio;
use DateTimeImmutable;

/**
 * Evento observado en el campo, con su fotografía (spec-incidencias.md). La campaña es opcional e informativa.
 */
final class Incidencia
{
    private const TOLERANCIA_FUTURO = '+5 minutes';

    private const VEN_TODAS = ['administrador', 'gerencia', 'lectura_operaciones'];

    public function __construct(
        public private(set) string $id,
        public private(set) TipoIncidencia $tipo,
        public private(set) string $descripcion,
        public private(set) DateTimeImmutable $fechaObservacion,
        public private(set) string $idParcela,
        public private(set) ?string $idCampania,
        public private(set) ReferenciaFoto $foto,
        public private(set) ?ClasificacionImagen $clasificacion,
        public private(set) Responsable $registradaPor,
        public private(set) DateTimeImmutable $fechaCreacion,
        public private(set) DateTimeImmutable $fechaRecepcion,
        public private(set) string $huella,
        public private(set) bool $notificacionPendiente,
        public private(set) int $version,
    ) {}

    public static function registrar(
        string $id,
        string $huella,
        TipoIncidencia $tipo,
        string $descripcion,
        DateTimeImmutable $fechaObservacion,
        DateTimeImmutable $fechaCreacion,
        string $idParcela,
        ?string $idCampania,
        ReferenciaFoto $foto,
        ?ClasificacionImagen $clasificacion,
        Responsable $registradaPor,
        DateTimeImmutable $ahora,
    ): self {
        self::validarFechas($fechaObservacion, $fechaCreacion, $ahora);

        // La notificación queda pendiente hasta que el broker confirme el evento (RQ-INC-08)
        return new self($id, $tipo, trim($descripcion), $fechaObservacion, $idParcela, $idCampania, $foto, $clasificacion,
            $registradaPor, $fechaCreacion, $ahora, $huella, true, 0);
    }

    public static function validarFechas(DateTimeImmutable $fechaObservacion, DateTimeImmutable $fechaCreacion, DateTimeImmutable $ahora): void
    {
        $limite = $ahora->modify(self::TOLERANCIA_FUTURO);
        if ($fechaObservacion > $limite || $fechaCreacion > $limite) {
            throw ExcepcionDominio::reglaNegocio('FECHA_OBSERVACION_INVALIDA', 'La fecha de observación no puede estar en el futuro.');
        }
    }

    /** RQ-INC-12 */
    public function puedeVerla(string $idUsuario, array $roles): bool
    {
        return array_intersect(self::VEN_TODAS, $roles) !== []
            || (in_array('tecnico_campo', $roles, true) && $this->registradaPor->id === $idUsuario);
    }

    /**
     * @param  list<string>  $roles
     */
    public static function veTodas(array $roles): bool
    {
        return array_intersect(self::VEN_TODAS, $roles) !== [];
    }
}
