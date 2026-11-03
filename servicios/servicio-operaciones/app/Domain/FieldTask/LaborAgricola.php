<?php

namespace App\Domain\FieldTask;

use App\Domain\Saga\EstadoSaga;
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
     * @param  list<string>  $idsSagaAnteriores  Sagas de intentos anteriores (decisión REINTENTAR)
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
        public private(set) ?Resolucion $resolucion = null,
        public private(set) array $idsSagaAnteriores = [],
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

    /** RN-07: realizada con insumos, campaña validada y todavía sin Saga. */
    public function requiereSaga(): bool
    {
        return $this->estado === EstadoLabor::PENDIENTE
            && $this->validacionCampania === ValidacionCampania::VALIDADA
            && $this->insumos !== []
            && $this->idSaga === null;
    }

    /** Se guarda en la misma escritura que la Saga (RQ-SAG-01); no es un cambio aparte, así que no sube la versión. */
    public function iniciarSaga(string $idSaga): void
    {
        if (! $this->requiereSaga()) {
            throw new \LogicException("La labor {$this->id} no requiere Saga.");
        }
        $this->idSaga = $idSaga;
    }

    /**
     * El administrador resuelve una labor en revisión según cómo terminó su Saga (spec-revision-labores.md RQ-REV-02 y RQ-REV-03).
     */
    public function resolver(
        DecisionRevision $decision,
        string $observacion,
        Responsable $administrador,
        EstadoSaga $estadoSaga,
        DateTimeImmutable $ahora,
    ): void {
        if ($this->estado !== EstadoLabor::PENDIENTE_REVISION) {
            throw ExcepcionDominio::reglaNegocio('LABOR_NO_EN_REVISION', 'Solo se resuelven labores en estado PENDIENTE_REVISION.');
        }
        if ($estadoSaga->activa()) {
            throw ExcepcionDominio::conflicto('SAGA_EN_CURSO', 'La Saga de la labor todavía está compensando; espere a que termine.');
        }
        $permitidas = self::decisionesPermitidas($estadoSaga);
        if (! in_array($decision, $permitidas, true)) {
            throw ExcepcionDominio::reglaNegocio(
                'DECISION_NO_PERMITIDA',
                "La decisión {$decision->value} no corresponde a una Saga {$estadoSaga->value}.",
                [['decisionesPermitidas' => array_map(fn (DecisionRevision $d) => $d->value, $permitidas)]],
            );
        }

        $observacion = trim($observacion);
        $this->resolucion = new Resolucion($decision, $observacion, $administrador, $ahora, $this->motivo);
        match ($decision) {
            // El descuento y el costo siguen vigentes y son coherentes (anulación rechazada)
            DecisionRevision::CONFIRMAR => [$this->estado, $this->motivo] = [EstadoLabor::CONFIRMADA, null],
            DecisionRevision::RECHAZAR => [$this->estado, $this->motivo] = [EstadoLabor::RECHAZADA, new Motivo(
                'RECHAZADA_EN_REVISION',
                "El administrador rechazó la labor en la revisión: {$observacion}",
            )],
            // Saga nueva: la anterior queda en el historial y sus respuestas tardías no afectan a la labor
            DecisionRevision::REINTENTAR => $this->prepararReintento(),
        };
        $this->tocar($ahora);
    }

    /**
     * @return list<DecisionRevision>
     */
    public static function decisionesPermitidas(EstadoSaga $estadoSaga): array
    {
        return match ($estadoSaga) {
            EstadoSaga::COMPENSADA => [DecisionRevision::RECHAZAR, DecisionRevision::REINTENTAR],
            EstadoSaga::REQUIERE_INTERVENCION => [DecisionRevision::CONFIRMAR],
            default => [],
        };
    }

    private function prepararReintento(): void
    {
        $this->idsSagaAnteriores[] = (string) $this->idSaga;
        $this->idSaga = null;
        $this->estado = EstadoLabor::PENDIENTE;
        $this->motivo = null;
    }

    /** Para iniciar la Saga de una labor ya guardada (sagas:iniciar-pendientes): ahí sí es un cambio aparte. */
    public function confirmarCambioAparte(DateTimeImmutable $ahora): void
    {
        $this->tocar($ahora);
    }

    /**
     * Resultado de la Saga (spec-saga.md RQ-SAG-04 y RQ-SAG-05): estado nuevo, motivo nuevo o ambos.
     */
    public function registrarResultadoSaga(?EstadoLabor $estado, ?Motivo $motivo, DateTimeImmutable $ahora): void
    {
        if (! in_array($this->estado, [EstadoLabor::PENDIENTE, EstadoLabor::PENDIENTE_REVISION], true)) {
            throw new \LogicException("La labor {$this->id} ya no espera el resultado de la Saga.");
        }
        $this->estado = $estado ?? $this->estado;
        $this->motivo = $motivo ?? ($estado === EstadoLabor::CONFIRMADA ? null : $this->motivo);
        $this->tocar($ahora);
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
