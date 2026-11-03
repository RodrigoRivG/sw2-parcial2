<?php

namespace App\Application\UseCases\ResolveReview;

use App\Application\Contracts\ConflictoEscritura;
use App\Application\Contracts\RegistroAuditoria;
use App\Application\Contracts\Reloj;
use App\Application\Contracts\UnidadTrabajo;
use App\Application\Security\SinPermiso;
use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\RegisterFieldTask\VerificadorCampania;
use App\Application\UseCases\Saga\IniciarSaga;
use App\Domain\FieldTask\DecisionRevision;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\RepositorioLabor;
use App\Domain\FieldTask\Responsable;
use App\Domain\Saga\RepositorioSaga;
use App\Domain\Shared\ExcepcionDominio;

/**
 * El administrador resuelve una labor PENDIENTE_REVISION (spec-revision-labores.md).
 */
final class ResolverRevisionCasoUso
{
    public function __construct(
        private readonly RepositorioLabor $labores,
        private readonly RepositorioSaga $sagas,
        private readonly UnidadTrabajo $unidadTrabajo,
        private readonly RegistroAuditoria $auditoria,
        private readonly VerificadorCampania $verificador,
        private readonly IniciarSaga $iniciarSaga,
        private readonly Reloj $reloj,
    ) {}

    public function ejecutar(ResolverRevisionEntrada $entrada, UsuarioAutenticado $usuario): LaborAgricola
    {
        if (! $usuario->tieneRol('administrador')) {
            throw new SinPermiso('Solo un administrador resuelve labores en revisión.');
        }

        $labor = $this->labores->buscar(strtolower($entrada->idLabor))
            ?? throw ExcepcionDominio::noEncontrado('LABOR_NO_ENCONTRADA', 'La labor no existe.');
        // Primero la versión: dos administradores que leyeron lo mismo no deben pisarse (RQ-REV-05)
        if ($labor->version !== $entrada->version) {
            throw self::conflicto();
        }
        $saga = $labor->idSaga === null ? null : $this->sagas->buscar($labor->idSaga);
        if ($saga === null) {
            throw ExcepcionDominio::reglaNegocio('LABOR_NO_EN_REVISION', 'Solo se resuelven labores en estado PENDIENTE_REVISION.');
        }
        if ($entrada->decision === DecisionRevision::REINTENTAR && $labor->estado === EstadoLabor::PENDIENTE_REVISION) {
            // Una campaña finalizada se rechaza en el momento; si gestión no responde, la Saga lo resolverá (RQ-REV-03)
            $this->verificador->exigir($labor->idCampania, $labor->idParcela);
        }

        $ahora = $this->reloj->ahora();
        $versionLeida = $labor->version;
        $labor->resolver($entrada->decision, $entrada->observacion, new Responsable($usuario->id, $usuario->nombre), $saga->estado, $ahora);
        $sagaNueva = $this->iniciarSaga->preparar($labor, $ahora);

        try {
            $this->unidadTrabajo->ejecutar(function () use ($labor, $versionLeida, $usuario, $sagaNueva) {
                $this->labores->actualizar($labor, $versionLeida, EstadoLabor::PENDIENTE_REVISION);
                $this->auditoria->registrar($usuario->id, 'RESOLVER_LABOR', 'LABOR', $labor->id);
                $this->iniciarSaga->registrar($sagaNueva);
            });
        } catch (ConflictoEscritura) {
            throw self::conflicto();
        }
        $this->iniciarSaga->enviar($sagaNueva);

        return $labor;
    }

    private static function conflicto(): ExcepcionDominio
    {
        return ExcepcionDominio::conflicto('CONFLICTO_CONCURRENCIA', 'La labor cambió desde que se leyó. Vuelva a consultarla.');
    }
}
