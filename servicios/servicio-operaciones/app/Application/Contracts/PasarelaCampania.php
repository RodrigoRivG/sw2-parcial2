<?php

namespace App\Application\Contracts;

use App\Domain\FieldTask\CampaniaConsultada;

/**
 * Consulta del estado de una campaña a servicio-gestion: la única llamada síncrona permitida (constitución §7).
 */
interface PasarelaCampania
{
    /**
     * @return CampaniaConsultada|null null si la campaña no existe
     *
     * @throws CampaniaNoDisponible si gestión no responde a tiempo o responde un error (RQ-LAB-05)
     */
    public function consultar(string $idCampania): ?CampaniaConsultada;
}
