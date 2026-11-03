<?php

namespace App\Domain\FieldTask;

use App\Domain\Shared\ExcepcionDominio;
use App\Domain\Shared\Motivo;
use DateTimeImmutable;

/**
 * Labor agrícola (spec-labores.md). Toda labor pertenece a una parcela y a una campaña (RN-06);
 * una programada no tiene efectos; una realizada sin insumos se confirma; con insumos queda PENDIENTE (RN-07).
 */
final class LaborAgricola
{
    /** Tolerancia del reloj del dispositivo hacia el futuro (README D-04). */
    private const TOLERANCIA_FUTURO = '+5 minutes';

    /** Minutos de espera entre intentos de la validación diferida: 1, 2, 4, 8 y luego 15 (RQ-LAB-10). */
    private const ESPERAS_VALIDACION = [1, 2, 4, 8];

    private const ESPERA_MAXIMA_VALIDACION = 15;

    /**
     * @param  list<ConsumoInsumo>  $insumos
     */
    public function __construct(
        public private(set) string $id,
        public private(set) TipoLabor $tipoLabor,
        public private(set) string $idParcela,
        public private(set) string $idCampania,
        public private(set) EstadoLabor $estado,
        public private(set) ?string $fechaProgramada,
        public private(set) ?DateTimeImmutable $fechaEjecucion,
        public private(set) DateTimeImmutable $fechaCreacion,
        public private(set) DateTimeImmutable $fechaRecepcion,
        public private(set) ?DateTimeImmutable $fechaRecepcionEjecucion,
        public private(set) Responsable $responsable,
        public private(set) ?Responsable $programadaPor,
        public private(set) ?string $observaciones,
        public private(set) array $insumos,
        public private(set) ValidacionCampania $validacionCampania,
        public private(set) ?string $idSaga,
        public private(set) ?Motivo $motivo,
        public private(set) string $huellaCreacion,
        public private(set) ?string $idOperacionRealizacion,
        public private(set) ?string $huellaRealizacion,
        public private(set) int $intentosValidacion,
        public private(set) ?DateTimeImmutable $fechaProximoValidacion,
        public private(set) int $version,
        public private(set) DateTimeImmutable $fechaActualizacion,
    ) {}

    public static function programar(
        string $id,
        string $huella,
        TipoLabor $tipoLabor,
        string $idParcela,
        string $idCampania,
        string $fechaProgramada,
        DateTimeImmutable $fechaCreacion,
        ?string $observaciones,
        Responsable $responsable,
        ValidacionCampania $validacion,
        DateTimeImmutable $ahora,
    ): self {
        self::validarProgramacion($fechaProgramada, $fechaCreacion, $ahora);

        $labor = new self(
            $id, $tipoLabor, $idParcela, $idCampania, EstadoLabor::PROGRAMADA, $fechaProgramada, null, $fechaCreacion, $ahora, null,
            $responsable, $responsable, self::texto($observaciones), [], ValidacionCampania::VALIDADA, null, null, $huella, null, null,
            0, null, 0, $ahora,
        );
        if ($validacion === ValidacionCampania::PENDIENTE) {
            $labor->diferirValidacion($ahora);
        }

        return $labor;
    }

    /**
     * @param  list<ConsumoInsumo>  $insumos
     */
    public static function registrarRealizada(
        string $id,
        string $huella,
        TipoLabor $tipoLabor,
        string $idParcela,
        string $idCampania,
        DateTimeImmutable $fechaEjecucion,
        DateTimeImmutable $fechaCreacion,
        ?string $observaciones,
        array $insumos,
        Responsable $responsable,
        ValidacionCampania $validacion,
        DateTimeImmutable $ahora,
    ): self {
        self::validarEjecucion($fechaEjecucion, $fechaCreacion, $ahora);

        $labor = new self(
            $id, $tipoLabor, $idParcela, $idCampania, EstadoLabor::PENDIENTE, null, $fechaEjecucion, $fechaCreacion, $ahora, $ahora,
            $responsable, null, self::texto($observaciones), $insumos, ValidacionCampania::VALIDADA, null, null, $huella, null, null,
            0, null, 0, $ahora,
        );
        $labor->estado = $labor->estadoTrasValidar();
        if ($validacion === ValidacionCampania::PENDIENTE) {
            $labor->diferirValidacion($ahora);
        }

        return $labor;
    }

    /** RQ-LAB-03, para comprobarlo antes de consultar la campaña. */
    public static function validarProgramacion(string $fechaProgramada, DateTimeImmutable $fechaCreacion, DateTimeImmutable $ahora): void
    {
        if ($fechaCreacion > $ahora->modify(self::TOLERANCIA_FUTURO) || $fechaProgramada < $fechaCreacion->format('Y-m-d')) {
            throw ExcepcionDominio::reglaNegocio(
                'FECHA_PROGRAMADA_INVALIDA',
                'La fecha programada no puede ser anterior a la fecha en que se creó la labor, ni la creación estar en el futuro.',
            );
        }
    }

    /** RQ-LAB-03, para comprobarlo antes de consultar la campaña. */
    public static function validarEjecucion(DateTimeImmutable $fechaEjecucion, DateTimeImmutable $fechaCreacion, DateTimeImmutable $ahora): void
    {
        $limite = $ahora->modify(self::TOLERANCIA_FUTURO);
        if ($fechaEjecucion > $limite || $fechaCreacion > $limite) {
            throw ExcepcionDominio::reglaNegocio('FECHA_EJECUCION_INVALIDA', 'La fecha de ejecución no puede estar en el futuro.');
        }
    }

    /**
     * Registra como realizada una labor programada (RQ-LAB-07).
     *
     * @param  list<ConsumoInsumo>  $insumos
     */
    public function realizar(
        string $idOperacion,
        string $huella,
        DateTimeImmutable $fechaEjecucion,
        DateTimeImmutable $fechaCreacion,
        ?string $observaciones,
        array $insumos,
        Responsable $responsable,
        ValidacionCampania $validacion,
        DateTimeImmutable $ahora,
    ): void {
        $this->exigirProgramada();
        self::validarEjecucion($fechaEjecucion, $fechaCreacion, $ahora);

        $this->idOperacionRealizacion = $idOperacion;
        $this->huellaRealizacion = $huella;
        $this->fechaEjecucion = $fechaEjecucion;
        $this->fechaRecepcionEjecucion = $ahora;
        $this->responsable = $responsable;
        $this->observaciones = self::texto($observaciones) ?? $this->observaciones;
        $this->insumos = $insumos;
        $this->estado = $this->estadoTrasValidar();
        if ($validacion === ValidacionCampania::PENDIENTE) {
            $this->diferirValidacion($ahora);
        }
        $this->tocar($ahora);
    }

    public function exigirProgramada(): void
    {
        if ($this->estado !== EstadoLabor::PROGRAMADA) {
            throw ExcepcionDominio::reglaNegocio('LABOR_NO_PROGRAMADA', 'Solo se puede registrar la realización de una labor programada.');
        }
    }

    /**
     * Resultado de la validación diferida (RQ-LAB-10): sin rechazo, el estado que le corresponde; con rechazo, RECHAZADA.
     */
    public function aplicarValidacion(?Motivo $rechazo, DateTimeImmutable $ahora): void
    {
        $this->validacionCampania = ValidacionCampania::VALIDADA;
        $this->intentosValidacion = 0;
        $this->fechaProximoValidacion = null;
        if ($rechazo !== null) {
            $this->estado = EstadoLabor::RECHAZADA;
            $this->motivo = $rechazo;
        } else {
            $this->estado = $this->estadoTrasValidar();
        }
        $this->tocar($ahora);
    }

    /** servicio-gestion siguió sin responder: se programa el próximo intento. */
    public function posponerValidacion(DateTimeImmutable $ahora): void
    {
        $this->intentosValidacion++;
        $minutos = self::ESPERAS_VALIDACION[$this->intentosValidacion] ?? self::ESPERA_MAXIMA_VALIDACION;
        $this->fechaProximoValidacion = $ahora->modify("+{$minutos} minutes");
        $this->tocar($ahora);
    }

    public function validacionPendiente(): bool
    {
        return $this->validacionCampania === ValidacionCampania::PENDIENTE;
    }

    /** RQ-LAB-15: la fecha por la que se ordena y filtra. */
    public function fechaReferencia(): string
    {
        return $this->fechaEjecucion !== null
            ? $this->fechaEjecucion->format('Y-m-d\TH:i:s\Z')
            : (string) $this->fechaProgramada;
    }

    public function esDe(string $idUsuario): bool
    {
        return $this->responsable->id === $idUsuario || $this->programadaPor?->id === $idUsuario;
    }

    private function diferirValidacion(DateTimeImmutable $ahora): void
    {
        $this->estado = EstadoLabor::PENDIENTE;
        $this->validacionCampania = ValidacionCampania::PENDIENTE;
        $this->intentosValidacion = 0;
        $this->fechaProximoValidacion = $ahora->modify('+'.self::ESPERAS_VALIDACION[0].' minutes');
    }

    /** RQ-LAB-06 */
    private function estadoTrasValidar(): EstadoLabor
    {
        return match (true) {
            $this->fechaEjecucion === null => EstadoLabor::PROGRAMADA,
            $this->insumos === [] => EstadoLabor::CONFIRMADA,
            default => EstadoLabor::PENDIENTE,
        };
    }

    private function tocar(DateTimeImmutable $ahora): void
    {
        $this->version++;
        $this->fechaActualizacion = $ahora;
    }

    private static function texto(?string $texto): ?string
    {
        $recortado = $texto === null ? null : trim($texto);

        return $recortado === '' ? null : $recortado;
    }
}
