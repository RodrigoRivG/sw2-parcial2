<?php

namespace App\Application\UseCases\Saga;

use App\Application\Contracts\ConflictoEscritura;
use App\Application\Contracts\RegistroAuditoria;
use App\Application\Contracts\Reloj;
use App\Application\Contracts\UnidadTrabajo;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\RepositorioLabor;
use App\Domain\Saga\Decision;
use App\Domain\Saga\RepositorioSaga;
use App\Domain\Saga\Saga;
use DateTimeImmutable;
use Psr\Log\LoggerInterface;
use RuntimeException;

/**
 * Paso común de la respuesta y del vencimiento (spec-saga.md RQ-SAG-07): relee la Saga, deja que decida,
 * escribe Saga, labor y auditoría juntas condicionadas a su versión y, después, publica el comando siguiente.
 * Ante una escritura concurrente (otra respuesta o la recuperación), relee y vuelve a decidir.
 */
final class AvanceSaga
{
    public const ACTOR = 'servicio-operaciones';

    private const MAXIMO_CONFLICTOS = 5;

    public function __construct(
        private readonly RepositorioSaga $sagas,
        private readonly RepositorioLabor $labores,
        private readonly UnidadTrabajo $unidadTrabajo,
        private readonly RegistroAuditoria $auditoria,
        private readonly EnvioComandos $envio,
        private readonly Reloj $reloj,
        private readonly LoggerInterface $log,
    ) {}

    /**
     * @param  callable(Saga, DateTimeImmutable): Decision  $decidir
     * @return Decision|null null si la Saga no existe
     */
    public function avanzar(string $idSaga, callable $decidir): ?Decision
    {
        for ($intento = 1; $intento <= self::MAXIMO_CONFLICTOS; $intento++) {
            $saga = $this->sagas->buscar($idSaga);
            if ($saga === null) {
                return null;
            }
            $ahora = $this->reloj->ahora();
            $versionSaga = $saga->version;
            $decision = $decidir($saga, $ahora);
            if ($saga->version === $versionSaga) {
                return $decision;
            }

            $labor = $decision->cambiaLabor() ? $this->laborDe($saga) : null;
            $versionLabor = $labor?->version;
            $labor?->registrarResultadoSaga($decision->estadoLabor, $decision->motivoLabor, $ahora);

            try {
                $this->unidadTrabajo->ejecutar(function () use ($saga, $versionSaga, $labor, $versionLabor) {
                    $this->sagas->actualizar($saga, $versionSaga);
                    $this->auditoria->registrar(self::ACTOR, 'AVANZAR_SAGA', 'SAGA', $saga->idSaga);
                    if ($labor !== null) {
                        $this->labores->actualizar($labor, (int) $versionLabor);
                        $this->auditoria->registrar(self::ACTOR, 'ACTUALIZAR_LABOR_SAGA', 'LABOR', $labor->id);
                    }
                });
            } catch (ConflictoEscritura) {
                continue;
            }

            $this->log->info('Saga actualizada', [
                'idCorrelacion' => $saga->idSaga,
                'estado' => $saga->estado->value,
                'paso' => $saga->pasoActual->value,
                'estadoLabor' => $labor?->estado->value,
                'tardia' => $decision->tardia,
            ]);
            if ($decision->pasoAEnviar !== null) {
                $this->envio->enviar($saga, $decision->pasoAEnviar);
            }

            return $decision;
        }

        throw new RuntimeException("La Saga {$idSaga} cambió en cada intento de actualizarla.");
    }

    private function laborDe(Saga $saga): LaborAgricola
    {
        $labor = $this->labores->buscar($saga->idLabor)
            ?? throw new RuntimeException("La labor {$saga->idLabor} de la Saga {$saga->idSaga} no existe.");
        if ($labor->idSaga !== $saga->idSaga) {
            throw new RuntimeException("La labor {$labor->id} ya no pertenece a la Saga {$saga->idSaga}.");
        }

        return $labor;
    }
}
