<?php

namespace App\Application\UseCases\Saga;

use App\Application\Contracts\Reloj;
use App\Domain\Saga\ConfiguracionSaga;
use App\Domain\Saga\RepositorioSaga;
use App\Domain\Saga\Saga;
use DateTimeImmutable;
use Psr\Log\LoggerInterface;
use Throwable;

/**
 * Tarea programada de recuperación (spec-saga.md RQ-SAG-09, RNF-10): reenvía o compensa las Sagas vencidas.
 */
final class ReanudarSagasEstancadas
{
    private const MAXIMO_POR_EJECUCION = 100;

    public function __construct(
        private readonly RepositorioSaga $sagas,
        private readonly AvanceSaga $avance,
        private readonly ConfiguracionSaga $config,
        private readonly Reloj $reloj,
        private readonly LoggerInterface $log,
    ) {}

    /** @return int Sagas con un comando reenviado o una compensación iniciada */
    public function ejecutar(): int
    {
        $atendidas = 0;
        foreach ($this->sagas->vencidas($this->reloj->ahora(), self::MAXIMO_POR_EJECUCION) as $idSaga) {
            try {
                // Saga::vencer no hace nada si, al releerla, ya no está vencida (otra ejecución o una respuesta ganó)
                $decision = $this->avance->avanzar(
                    $idSaga,
                    fn (Saga $saga, DateTimeImmutable $ahora) => $saga->vencer($ahora, $this->config),
                );
                if ($decision?->pasoAEnviar !== null) {
                    $atendidas++;
                }
            } catch (Throwable $e) {
                // Una Saga con problemas no frena a las demás; se reintenta en la próxima ejecución
                $this->log->error('No se pudo reanudar la Saga', ['idCorrelacion' => $idSaga, 'error' => $e->getMessage()]);
            }
        }

        return $atendidas;
    }
}
