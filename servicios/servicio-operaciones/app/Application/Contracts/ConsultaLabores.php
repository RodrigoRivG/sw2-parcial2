<?php

namespace App\Application\Contracts;

use App\Application\UseCases\QueryFieldTasks\FiltroLabores;
use App\Domain\FieldTask\LaborAgricola;

/**
 * Listado de labores por los índices de spec-labores.md 2.3. No es un repositorio de agregado.
 */
interface ConsultaLabores
{
    /**
     * @return Pagina<LaborAgricola>
     *
     * @throws CursorInvalido
     */
    public function listar(FiltroLabores $filtro): Pagina;
}
