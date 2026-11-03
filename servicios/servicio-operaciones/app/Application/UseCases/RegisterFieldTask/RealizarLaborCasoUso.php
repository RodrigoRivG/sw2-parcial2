<?php

namespace App\Application\UseCases\RegisterFieldTask;

use App\Application\Contracts\ConflictoEscritura;
use App\Application\Contracts\RegistroAuditoria;
use App\Application\Contracts\Reloj;
use App\Application\Contracts\UnidadTrabajo;
use App\Application\Security\SinPermiso;
use App\Application\Security\UsuarioAutenticado;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\RepositorioLabor;
use App\Domain\FieldTask\Responsable;
use App\Domain\Shared\ExcepcionDominio;
use App\Domain\Shared\Huella;

/**
 * Registra como realizada una labor programada (spec-labores.md RQ-LAB-07), idempotente por su propio idOperacion.
 */
final class RealizarLaborCasoUso
{
    public function __construct(
        private readonly RepositorioLabor $repositorio,
        private readonly UnidadTrabajo $unidadTrabajo,
        private readonly RegistroAuditoria $auditoria,
        private readonly VerificadorCampania $verificador,
        private readonly Reloj $reloj,
    ) {}

    public function ejecutar(RealizarLaborEntrada $entrada, UsuarioAutenticado $usuario): ResultadoLabor
    {
        if (! $usuario->tieneRol('tecnico_campo')) {
            throw new SinPermiso('Solo un técnico de campo puede registrar la realización de una labor.');
        }

        $idLabor = strtolower($entrada->idLabor);
        $idOperacion = strtolower($entrada->idOperacion);
        $consumos = InsumosEntrada::aConsumos($entrada->insumos);
        $huella = Huella::calcular([
            'operacion' => 'REALIZAR_LABOR',
            'idLabor' => $idLabor,
            'idOperacion' => $idOperacion,
            'fechaCreacion' => $entrada->fechaCreacion->format('Y-m-d\TH:i:s\Z'),
            'fechaEjecucion' => $entrada->fechaEjecucion->format('Y-m-d\TH:i:s\Z'),
            'observaciones' => $entrada->observaciones,
            'insumos' => InsumosEntrada::paraHuella($consumos),
        ], $usuario->id);

        $labor = $this->buscar($idLabor);
        if ($idOperacion === $labor->id) {
            // Cada operación tiene su propio UUID: el de la creación no sirve para la realización
            throw CreacionLabor::conflictoIdempotencia();
        }
        $repetida = $this->repeticion($labor, $idOperacion, $huella);
        if ($repetida !== null) {
            return $repetida;
        }

        $ahora = $this->reloj->ahora();
        $labor->exigirProgramada();
        LaborAgricola::validarEjecucion($entrada->fechaEjecucion, $entrada->fechaCreacion, $ahora);
        $validacion = $this->verificador->exigir($labor->idCampania, $labor->idParcela);

        $versionLeida = $labor->version;
        $labor->realizar(
            $idOperacion,
            $huella,
            $entrada->fechaEjecucion,
            $entrada->fechaCreacion,
            $entrada->observaciones,
            $consumos,
            new Responsable($usuario->id, $usuario->nombre),
            $validacion,
            $ahora,
        );

        try {
            $this->unidadTrabajo->ejecutar(function () use ($labor, $versionLeida, $usuario) {
                $this->repositorio->actualizar($labor, $versionLeida, EstadoLabor::PROGRAMADA);
                $this->auditoria->registrar($usuario->id, 'REALIZAR_LABOR', 'LABOR', $labor->id);
            });
        } catch (ConflictoEscritura) {
            $actual = $this->buscar($idLabor);
            $repetida = $this->repeticion($actual, $idOperacion, $huella);
            if ($repetida !== null) {
                return $repetida;
            }
            $actual->exigirProgramada();

            throw ExcepcionDominio::conflicto('CONFLICTO_CONCURRENCIA', 'La labor cambió mientras se registraba su realización. Intente nuevamente.');
        }

        return new ResultadoLabor($labor, false);
    }

    private function buscar(string $idLabor): LaborAgricola
    {
        return $this->repositorio->buscar($idLabor)
            ?? throw ExcepcionDominio::noEncontrado('LABOR_NO_ENCONTRADA', 'La labor no existe.');
    }

    private function repeticion(LaborAgricola $labor, string $idOperacion, string $huella): ?ResultadoLabor
    {
        if ($labor->idOperacionRealizacion !== $idOperacion) {
            return null;
        }
        if (! hash_equals((string) $labor->huellaRealizacion, $huella)) {
            throw CreacionLabor::conflictoIdempotencia();
        }

        return new ResultadoLabor($labor, true);
    }
}
