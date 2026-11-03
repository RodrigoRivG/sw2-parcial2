<?php

namespace App\Application\UseCases\RevalidateCampaign;

use App\Application\Contracts\ConflictoEscritura;
use App\Application\Contracts\RegistroAuditoria;
use App\Application\Contracts\Reloj;
use App\Application\Contracts\UnidadTrabajo;
use App\Application\UseCases\RegisterFieldTask\VerificadorCampania;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\RepositorioLabor;

/**
 * Tarea programada: revalida las labores cuya consulta de campaña quedó diferida (spec-labores.md RQ-LAB-10).
 */
final class RevalidarCampaniasCasoUso
{
    public const ACTOR = 'servicio-operaciones';

    private const MAXIMO_POR_EJECUCION = 100;

    public function __construct(
        private readonly RepositorioLabor $repositorio,
        private readonly UnidadTrabajo $unidadTrabajo,
        private readonly RegistroAuditoria $auditoria,
        private readonly VerificadorCampania $verificador,
        private readonly Reloj $reloj,
    ) {}

    /**
     * @return array{validadas: int, rechazadas: int, pospuestas: int}
     */
    public function ejecutar(): array
    {
        $resumen = ['validadas' => 0, 'rechazadas' => 0, 'pospuestas' => 0];
        $ahora = $this->reloj->ahora();

        foreach ($this->repositorio->conValidacionVencida($ahora, self::MAXIMO_POR_EJECUCION) as $labor) {
            $resultado = $this->verificador->verificar($labor->idCampania, $labor->idParcela);
            $versionLeida = $labor->version;

            if (! $resultado->disponible) {
                $labor->posponerValidacion($ahora);
                $clave = 'pospuestas';
            } else {
                $labor->aplicarValidacion($resultado->rechazo, $ahora);
                $clave = $resultado->rechazo === null ? 'validadas' : 'rechazadas';
            }

            if ($this->guardar($labor, $versionLeida, auditar: $resultado->disponible)) {
                $resumen[$clave]++;
            }
        }

        return $resumen;
    }

    private function guardar(LaborAgricola $labor, int $versionLeida, bool $auditar): bool
    {
        try {
            $this->unidadTrabajo->ejecutar(function () use ($labor, $versionLeida, $auditar) {
                $this->repositorio->actualizar($labor, $versionLeida);
                if ($auditar) {
                    $this->auditoria->registrar(self::ACTOR, 'VALIDAR_CAMPANIA', 'LABOR', $labor->id);
                }
            });

            return true;
        } catch (ConflictoEscritura) {
            // Otra ejecución de la tarea ya la procesó (Historia 4, escenario 5)
            return false;
        }
    }
}
