<?php

namespace App\Application\UseCases\Saga;

use App\Application\Contracts\ConflictoEscritura;
use App\Application\Contracts\Reloj;
use App\Application\Contracts\UnidadTrabajo;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\RepositorioLabor;

/**
 * Inicia la Saga de las labores PENDIENTE con insumos que se registraron antes de existir la Saga (spec-saga.md, casos borde).
 */
final class IniciarSagasPendientes
{
    private const MAXIMO_POR_EJECUCION = 100;

    public function __construct(
        private readonly RepositorioLabor $labores,
        private readonly IniciarSaga $iniciarSaga,
        private readonly UnidadTrabajo $unidadTrabajo,
        private readonly Reloj $reloj,
    ) {}

    public function ejecutar(): int
    {
        $iniciadas = 0;
        foreach ($this->labores->pendientesSinSaga(self::MAXIMO_POR_EJECUCION) as $labor) {
            $versionLeida = $labor->version;
            $saga = $this->iniciarSaga->preparar($labor, $this->reloj->ahora());
            if ($saga === null) {
                continue;
            }
            $labor->confirmarCambioAparte($this->reloj->ahora());
            try {
                $this->unidadTrabajo->ejecutar(function () use ($labor, $versionLeida, $saga) {
                    $this->labores->actualizar($labor, $versionLeida, EstadoLabor::PENDIENTE);
                    $this->iniciarSaga->registrar($saga);
                });
            } catch (ConflictoEscritura) {
                // Otra ejecución ya le inició la Saga
                continue;
            }
            $this->iniciarSaga->enviar($saga);
            $iniciadas++;
        }

        return $iniciadas;
    }
}
