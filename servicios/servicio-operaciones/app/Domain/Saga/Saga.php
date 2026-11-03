<?php

namespace App\Domain\Saga;

use App\Domain\FieldTask\ConsumoInsumo;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\Shared\Motivo;
use DateTimeImmutable;

/**
 * Saga labor → descuento de insumos → registro de costo, con sus compensaciones (constitución §6, spec-saga.md).
 * Es la única que decide: los casos de uso leen, le pasan la respuesta o el vencimiento, escriben y publican.
 */
final class Saga
{
    /** Respuestas tardías que se conservan (límite de 400 KB por ítem de DynamoDB). */
    public const MAXIMO_TARDIAS = 20;

    /**
     * @param  list<ConsumoInsumo>  $items
     * @param  array<string, RegistroPaso>  $pasos  indexados por el valor de PasoSaga
     * @param  list<array{tipo: string, idMensaje: string, codigo: ?string, fechaRecepcion: string}>  $respuestasTardias
     */
    public function __construct(
        public private(set) string $idSaga,
        public private(set) string $idLabor,
        public private(set) string $idCampania,
        public private(set) array $items,
        public private(set) EstadoSaga $estado,
        public private(set) PasoSaga $pasoActual,
        public private(set) ?string $costoTotal,
        public private(set) array $pasos,
        public private(set) array $respuestasTardias,
        public private(set) DateTimeImmutable $fechaLimite,
        public private(set) int $version,
        public private(set) DateTimeImmutable $fechaCreacion,
        public private(set) DateTimeImmutable $fechaActualizacion,
    ) {}

    public function __clone()
    {
        $this->pasos = array_map(fn (RegistroPaso $paso) => clone $paso, $this->pasos);
    }

    /** RQ-SAG-01: la Saga empieza con DescontarInsumos enviado. */
    public static function iniciar(string $idSaga, LaborAgricola $labor, DateTimeImmutable $ahora, ConfiguracionSaga $config): self
    {
        return new self(
            $idSaga, $labor->id, $labor->idCampania, $labor->insumos, EstadoSaga::EN_CURSO, PasoSaga::DESCONTAR_INSUMOS, null,
            [PasoSaga::DESCONTAR_INSUMOS->value => RegistroPaso::enviado($ahora)], [],
            $ahora->modify("+{$config->tiempoLimiteSegundos} seconds"), 0, $ahora, $ahora,
        );
    }

    /** RQ-SAG-04 */
    public function aplicarRespuesta(RespuestaSaga $respuesta, DateTimeImmutable $ahora, ConfiguracionSaga $config): Decision
    {
        $esperada = $this->estado->activa()
            && $respuesta->tipo->paso() === $this->pasoActual
            && $this->paso($this->pasoActual)->estado === EstadoPaso::ENVIADO;
        if (! $esperada) {
            return $this->registrarTardia($respuesta, $ahora);
        }

        $this->paso($this->pasoActual)->responder($respuesta, $ahora);

        $decision = match ($respuesta->tipo) {
            TipoRespuesta::INSUMOS_DESCONTADOS => $this->alDescontar($respuesta, $ahora, $config),
            TipoRespuesta::INSUMOS_RECHAZADOS => $this->terminar(EstadoSaga::RECHAZADA, new Decision(
                EstadoLabor::RECHAZADA,
                new Motivo((string) $respuesta->codigo, (string) $respuesta->motivo, $respuesta->detalles),
            )),
            TipoRespuesta::COSTO_REGISTRADO => $this->terminar(EstadoSaga::COMPLETADA, new Decision(EstadoLabor::CONFIRMADA)),
            TipoRespuesta::COSTO_RECHAZADO => $this->compensar(PasoSaga::RESTAURAR_INSUMOS, $ahora, $config, new Motivo(
                'COSTO_RECHAZADO',
                'servicio-gestion rechazó el costo de la labor; se devuelven los insumos al inventario.',
                [['codigo' => $respuesta->codigo, 'motivo' => $respuesta->motivo]],
            )),
            TipoRespuesta::COSTO_ANULADO => new Decision(pasoAEnviar: $this->enviar(PasoSaga::RESTAURAR_INSUMOS, $ahora, $config)),
            TipoRespuesta::ANULACION_RECHAZADA => $this->terminar(EstadoSaga::REQUIERE_INTERVENCION, new Decision(
                motivoLabor: new Motivo(
                    'ANULACION_COSTO_RECHAZADA',
                    'La campaña ya estaba finalizada con el costo registrado: el descuento y el costo siguen vigentes. Lo resuelve el administrador.',
                    [['codigo' => $respuesta->codigo, 'motivo' => $respuesta->motivo]],
                ),
            )),
            TipoRespuesta::INSUMOS_RESTAURADOS => $this->terminar(EstadoSaga::COMPENSADA, new Decision),
        };

        $this->tocar($ahora);

        return $decision;
    }

    /** RQ-SAG-05: se llama cuando la fecha límite venció. */
    public function vencer(DateTimeImmutable $ahora, ConfiguracionSaga $config): Decision
    {
        $paso = $this->paso($this->pasoActual);
        if (! $this->estaVencida($ahora) || $paso->estado !== EstadoPaso::ENVIADO) {
            return new Decision;
        }

        if ($this->pasoActual->esCompensacion() || $paso->intentos < $config->maximoEnvios) {
            $paso->reenviar($ahora);
            $this->fechaLimite = $ahora->modify('+'.$this->espera($paso->intentos, $config).' seconds');
            $this->tocar($ahora);

            return new Decision(pasoAEnviar: $this->pasoActual);
        }

        $paso->agotar("Sin respuesta después de {$paso->intentos} envíos.");
        $decision = $this->pasoActual === PasoSaga::DESCONTAR_INSUMOS
            // No se sabe si inventario descontó: se compensa igual (constitución §6)
            ? $this->compensar(PasoSaga::RESTAURAR_INSUMOS, $ahora, $config, new Motivo(
                'SIN_RESPUESTA_INVENTARIO',
                'servicio-inventario no respondió al descuento de insumos; se pidió devolverlos por si se descontaron.',
            ))
            // No se sabe si gestión registró el costo: primero se anula y recién después se restauran los insumos
            : $this->compensar(PasoSaga::ANULAR_COSTO, $ahora, $config, new Motivo(
                'SIN_RESPUESTA_GESTION',
                'servicio-gestion no respondió al registro del costo; se pidió anularlo antes de devolver los insumos.',
            ));
        $this->tocar($ahora);

        return $decision;
    }

    public function estaVencida(DateTimeImmutable $ahora): bool
    {
        return $this->estado->activa() && $this->fechaLimite <= $ahora;
    }

    public function paso(PasoSaga $paso): RegistroPaso
    {
        return $this->pasos[$paso->value];
    }

    private function alDescontar(RespuestaSaga $respuesta, DateTimeImmutable $ahora, ConfiguracionSaga $config): Decision
    {
        $this->costoTotal = (string) $respuesta->costoTotal;
        if (bccomp($this->costoTotal, '0', 2) === 0) {
            // gestión solo admite montos mayores a 0: no hay costo que registrar (constitución v2.5.0)
            $this->pasos[PasoSaga::REGISTRAR_COSTO->value] = RegistroPaso::omitido($ahora);
            $this->pasoActual = PasoSaga::REGISTRAR_COSTO;

            return $this->terminar(EstadoSaga::COMPLETADA, new Decision(EstadoLabor::CONFIRMADA));
        }

        return new Decision(pasoAEnviar: $this->enviar(PasoSaga::REGISTRAR_COSTO, $ahora, $config));
    }

    private function compensar(PasoSaga $paso, DateTimeImmutable $ahora, ConfiguracionSaga $config, Motivo $motivo): Decision
    {
        $this->estado = EstadoSaga::COMPENSANDO;

        return new Decision(EstadoLabor::PENDIENTE_REVISION, $motivo, $this->enviar($paso, $ahora, $config));
    }

    private function enviar(PasoSaga $paso, DateTimeImmutable $ahora, ConfiguracionSaga $config): PasoSaga
    {
        $this->pasos[$paso->value] = RegistroPaso::enviado($ahora);
        $this->pasoActual = $paso;
        $this->fechaLimite = $ahora->modify('+'.$this->espera(1, $config).' seconds');

        return $paso;
    }

    private function terminar(EstadoSaga $estado, Decision $decision): Decision
    {
        $this->estado = $estado;

        return $decision;
    }

    /** Pasos hacia adelante: siempre el tiempo límite; compensaciones: se duplica en cada envío hasta el máximo. */
    private function espera(int $envios, ConfiguracionSaga $config): int
    {
        if (! $this->pasoActual->esCompensacion()) {
            return $config->tiempoLimiteSegundos;
        }

        return min($config->tiempoLimiteSegundos * (2 ** ($envios - 1)), $config->esperaMaximaCompensacionSegundos);
    }

    private function registrarTardia(RespuestaSaga $respuesta, DateTimeImmutable $ahora): Decision
    {
        $this->respuestasTardias[] = [
            'tipo' => $respuesta->tipo->value,
            'idMensaje' => $respuesta->idMensaje,
            'codigo' => $respuesta->codigo,
            'fechaRecepcion' => $ahora->format('Y-m-d\TH:i:s\Z'),
        ];
        $this->respuestasTardias = array_slice($this->respuestasTardias, -self::MAXIMO_TARDIAS);
        $this->tocar($ahora);

        return new Decision(tardia: true);
    }

    private function tocar(DateTimeImmutable $ahora): void
    {
        $this->version++;
        $this->fechaActualizacion = $ahora;
    }
}
