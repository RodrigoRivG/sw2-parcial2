<?php

namespace App\Application\Contracts;

use App\Application\UseCases\QueryIncidents\FiltroIncidencias;
use App\Domain\Incident\Incidencia;

/**
 * Listado de incidencias por los índices de spec-incidencias.md 2.3.
 */
interface ConsultaIncidencias
{
    /**
     * @return Pagina<Incidencia>
     *
     * @throws CursorInvalido
     */
    public function listar(FiltroIncidencias $filtro): Pagina;
}
