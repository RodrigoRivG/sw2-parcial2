<?php

namespace App\Application\UseCases\SyncOfflineOperations;

use App\Application\Security\SinPermiso;
use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\RegisterFieldTask\RealizarLaborCasoUso;
use App\Application\UseCases\RegisterFieldTask\RealizarLaborEntrada;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborCasoUso;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborEntrada;
use App\Application\UseCases\RegisterIncident\RegistrarIncidenciaCasoUso;
use App\Application\UseCases\RegisterIncident\RegistrarIncidenciaEntrada;
use App\Application\UseCases\ScheduleFieldTask\ProgramarLaborCasoUso;
use App\Application\UseCases\ScheduleFieldTask\ProgramarLaborEntrada;
use App\Domain\Shared\ExcepcionDominio;
use Psr\Log\LoggerInterface;
use Throwable;

/**
 * Procesa un lote de operaciones offline en orden cronológico con los mismos casos de uso de cada endpoint
 * (spec-sincronizacion.md 2.2). El fallo de una operación no aborta el lote (constitución §5).
 */
final class SincronizarOperacionesCasoUso
{
    public function __construct(
        private readonly ProgramarLaborCasoUso $programar,
        private readonly RegistrarLaborCasoUso $registrar,
        private readonly RealizarLaborCasoUso $realizar,
        private readonly RegistrarIncidenciaCasoUso $registrarIncidencia,
        private readonly PasarelaCampaniaConCache $campanias,
        private readonly LoggerInterface $log,
    ) {}

    /**
     * @param  list<OperacionSincronizacion>  $operaciones
     * @return list<ResultadoOperacion> en el orden en que se procesaron
     */
    public function ejecutar(array $operaciones, UsuarioAutenticado $usuario, string $idCorrelacion): array
    {
        $validas = array_values(array_filter($operaciones, fn (OperacionSincronizacion $o) => $o->sobreValido()));
        $sinSobre = array_values(array_filter($operaciones, fn (OperacionSincronizacion $o) => ! $o->sobreValido()));
        // RQ-SIN-03: por fecha de creación en el dispositivo y, a igual fecha, por idOperacion
        usort($validas, fn (OperacionSincronizacion $a, OperacionSincronizacion $b) => [$a->fechaCreacion, $a->idOperacion] <=> [$b->fechaCreacion, $b->idOperacion]);

        $resultados = [];
        $this->campanias->activar();
        try {
            foreach ($validas as $operacion) {
                $resultados[] = $this->procesar($operacion, $usuario, $idCorrelacion);
            }
        } finally {
            $this->campanias->desactivar();
        }

        foreach ($sinSobre as $operacion) {
            $resultados[] = self::rechazo($operacion);
        }

        return $resultados;
    }

    private function procesar(OperacionSincronizacion $operacion, UsuarioAutenticado $usuario, string $idCorrelacion): ResultadoOperacion
    {
        if ($operacion->entrada === null) {
            return self::rechazo($operacion);
        }

        try {
            $entrada = $operacion->entrada;
            if ($entrada instanceof RegistrarIncidenciaEntrada) {
                $resultado = $this->registrarIncidencia->ejecutar($entrada, $usuario);

                return ResultadoOperacion::sincronizada($operacion, $resultado->repetida, $resultado->incidencia->id, null);
            }
            $resultado = match (true) {
                $entrada instanceof ProgramarLaborEntrada => $this->programar->ejecutar($entrada, $usuario),
                $entrada instanceof RegistrarLaborEntrada => $this->registrar->ejecutar($entrada, $usuario),
                $entrada instanceof RealizarLaborEntrada => $this->realizar->ejecutar($entrada, $usuario),
            };

            return ResultadoOperacion::sincronizada($operacion, $resultado->repetida, $resultado->labor->id, $resultado->labor->estado->value);
        } catch (ExcepcionDominio $e) {
            return ResultadoOperacion::error($operacion, $e->codigo, $e->getMessage(), $e->detalles);
        } catch (SinPermiso $e) {
            return ResultadoOperacion::error($operacion, 'SIN_PERMISO', $e->getMessage());
        } catch (Throwable $e) {
            // RQ-SIN-05: un fallo técnico se informa como reintentable; la app conserva la operación y la reenvía
            $this->log->error('Fallo técnico al sincronizar una operación', [
                'idCorrelacion' => $idCorrelacion,
                'idOperacion' => $operacion->idOperacion,
                'tipo' => $operacion->tipo,
                'error' => $e->getMessage(),
            ]);

            return ResultadoOperacion::error($operacion, 'ERROR_INTERNO', 'Ocurrió un error inesperado. Intente nuevamente.', [], true);
        }
    }

    private static function rechazo(OperacionSincronizacion $operacion): ResultadoOperacion
    {
        $error = $operacion->error;

        return ResultadoOperacion::error(
            $operacion,
            $error->codigo ?? 'DATOS_INVALIDOS',
            $error->mensaje ?? 'La operación no tiene tipo, idOperacion o fechaCreacion válidos.',
            $error->detalles ?? [],
        );
    }
}
