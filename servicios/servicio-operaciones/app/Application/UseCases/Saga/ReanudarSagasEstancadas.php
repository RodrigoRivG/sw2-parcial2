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
 *
 * Presupuesto para iniciar trabajo (RQ-SAG-14): antes de tomar cada Saga se mide el tiempo transcurrido con un
 * reloj monotónico; si pasó el presupuesto, no se toman más y las restantes quedan para la siguiente ejecución.
 * No es un límite de duración: la consulta inicial o la última Saga iniciada pueden prolongar la ejecución.
 */
final class ReanudarSagasEstancadas
{
    private const MAXIMO_POR_EJECUCION = 100;

    public const PRESUPUESTO_SEGUNDOS = 8.0;

    /** @var callable(): float Segundos de un reloj monotónico */
    private $cronometro;

    public function __construct(
        private readonly RepositorioSaga $sagas,
        private readonly AvanceSaga $avance,
        private readonly ConfiguracionSaga $config,
        private readonly Reloj $reloj,
        private readonly LoggerInterface $log,
        ?callable $cronometro = null,
    ) {
        $this->cronometro = $cronometro ?? static fn (): float => hrtime(true) / 1e9;
    }

    /** @return int Sagas con un comando reenviado o una compensación iniciada */
    public function ejecutar(): int
    {
        $atendidas = 0;
        $inicio = ($this->cronometro)();
        $vencidas = $this->sagas->vencidas($this->reloj->ahora(), self::MAXIMO_POR_EJECUCION);
        foreach ($vencidas as $indice => $idSaga) {
            if (($this->cronometro)() - $inicio >= self::PRESUPUESTO_SEGUNDOS) {
                $this->log->info('Presupuesto de la recuperación agotado; las Sagas restantes quedan para la siguiente ejecución', [
                    'pendientes' => count($vencidas) - $indice,
                ]);
                break;
            }
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
