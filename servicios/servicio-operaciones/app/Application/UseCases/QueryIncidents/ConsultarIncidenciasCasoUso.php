<?php

namespace App\Application\UseCases\QueryIncidents;

use App\Application\Contracts\AlmacenamientoArchivos;
use App\Application\Contracts\ConsultaIncidencias;
use App\Application\Contracts\Pagina;
use App\Application\Security\SinPermiso;
use App\Application\Security\UsuarioAutenticado;
use App\Domain\Incident\Incidencia;
use App\Domain\Incident\RepositorioIncidencia;
use App\Domain\Shared\ExcepcionDominio;

/**
 * Detalle y listado de incidencias, cada una con una URL prefirmada de 10 minutos (RQ-INC-11).
 */
final class ConsultarIncidenciasCasoUso
{
    public const MINUTOS_URL = 10;

    public function __construct(
        private readonly RepositorioIncidencia $repositorio,
        private readonly ConsultaIncidencias $consulta,
        private readonly AlmacenamientoArchivos $almacenamiento,
    ) {}

    public function detalle(string $id, UsuarioAutenticado $usuario): IncidenciaConFoto
    {
        $incidencia = $this->repositorio->buscar(strtolower($id))
            ?? throw ExcepcionDominio::noEncontrado('INCIDENCIA_NO_ENCONTRADA', 'La incidencia no existe.');
        if (! $incidencia->puedeVerla($usuario->id, $usuario->roles)) {
            throw new SinPermiso('Solo puede ver las incidencias que registró.');
        }

        return $this->conFoto($incidencia);
    }

    /**
     * @return Pagina<IncidenciaConFoto>
     */
    public function listar(FiltroIncidencias $filtro, bool $mias, UsuarioAutenticado $usuario): Pagina
    {
        if ($mias) {
            $filtro = $filtro->conRegistrador($usuario->id);
        } elseif (! Incidencia::veTodas($usuario->roles)) {
            throw new SinPermiso('Un técnico de campo solo puede listar sus incidencias (mias=true).');
        }

        $pagina = $this->consulta->listar($filtro);

        return new Pagina(array_map(fn (Incidencia $i) => $this->conFoto($i), $pagina->items), $pagina->siguienteCursor);
    }

    private function conFoto(Incidencia $incidencia): IncidenciaConFoto
    {
        return new IncidenciaConFoto($incidencia, $this->almacenamiento->urlTemporal($incidencia->foto->clave, self::MINUTOS_URL));
    }
}
