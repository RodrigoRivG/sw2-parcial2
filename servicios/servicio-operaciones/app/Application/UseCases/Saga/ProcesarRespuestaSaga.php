<?php

namespace App\Application\UseCases\Saga;

use App\Domain\Saga\ConfiguracionSaga;
use App\Domain\Saga\Decision;
use App\Domain\Saga\Saga;
use App\Domain\Saga\TipoRespuesta;
use DateTimeImmutable;
use Psr\Log\LoggerInterface;

/**
 * Aplica una respuesta de un participante (spec-saga.md RQ-SAG-03 y RQ-SAG-04).
 */
final class ProcesarRespuestaSaga
{
    public function __construct(
        private readonly AvanceSaga $avance,
        private readonly ConfiguracionSaga $config,
        private readonly LoggerInterface $log,
    ) {}

    /**
     * @param  array<string, mixed>  $datos
     *
     * @throws RespuestaInvalida si no se puede procesar con seguridad (va a la DLQ sin reintentos)
     */
    public function ejecutar(TipoRespuesta $tipo, string $idMensaje, string $idCorrelacion, array $datos): Decision
    {
        $respuesta = LectorRespuesta::leer($tipo, $idMensaje, $datos);
        if ($datos['idSaga'] !== $idCorrelacion) {
            throw new RespuestaInvalida('idCorrelacion distinto de datos.idSaga.');
        }

        $decision = $this->avance->avanzar(
            strtolower($idCorrelacion),
            fn (Saga $saga, DateTimeImmutable $ahora) => $saga->aplicarRespuesta($respuesta, $ahora, $this->config),
        ) ?? throw new RespuestaInvalida("La Saga {$idCorrelacion} no existe.");

        if ($decision->tardia) {
            $this->log->warning('Respuesta tardía o duplicada: se registra en la Saga sin cambiar la labor', [
                'idCorrelacion' => $idCorrelacion,
                'idMensaje' => $idMensaje,
                'tipo' => $tipo->value,
            ]);
        }

        return $decision;
    }
}
