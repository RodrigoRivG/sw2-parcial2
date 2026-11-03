<?php

namespace App\Application\UseCases\QueryFieldTasks;

use App\Application\Contracts\ConsultaLabores;
use App\Application\Contracts\Pagina;
use App\Application\Security\SinPermiso;
use App\Application\Security\UsuarioAutenticado;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\PoliticaVisibilidadLabor;
use App\Domain\FieldTask\RepositorioLabor;
use App\Domain\Shared\ExcepcionDominio;

/**
 * Detalle y listado de labores con la visibilidad de RQ-LAB-17.
 */
final class ConsultarLaboresCasoUso
{
    public function __construct(
        private readonly RepositorioLabor $repositorio,
        private readonly ConsultaLabores $consulta,
    ) {}

    public function detalle(string $id, UsuarioAutenticado $usuario): LaborAgricola
    {
        $labor = $this->repositorio->buscar(strtolower($id))
            ?? throw ExcepcionDominio::noEncontrado('LABOR_NO_ENCONTRADA', 'La labor no existe.');

        if (! PoliticaVisibilidadLabor::puedeVer($labor, $usuario->id, $usuario->roles)) {
            throw new SinPermiso('Solo puede ver las labores programadas y las suyas.');
        }

        return $labor;
    }

    /**
     * @return Pagina<LaborAgricola>
     */
    public function listar(FiltroLabores $filtro, bool $mias, UsuarioAutenticado $usuario): Pagina
    {
        if ($mias) {
            $filtro = $filtro->conResponsable($usuario->id);
        }

        if (! PoliticaVisibilidadLabor::veTodas($usuario->roles)) {
            $soloSuyas = $filtro->idResponsable === $usuario->id;
            if (! $soloSuyas && $filtro->estado !== EstadoLabor::PROGRAMADA) {
                throw new SinPermiso('Un técnico de campo solo puede listar sus labores (mias=true) o las programadas (estado=PROGRAMADA).');
            }
        }

        return $this->consulta->listar($filtro);
    }
}
