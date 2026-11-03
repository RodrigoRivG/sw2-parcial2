<?php

namespace App\Domain\FieldTask;

/**
 * Quién ve qué labor (spec-labores.md RQ-LAB-17).
 */
final class PoliticaVisibilidadLabor
{
    private const VEN_TODAS = ['administrador', 'gerencia', 'lectura_operaciones'];

    /**
     * @param  list<string>  $roles
     */
    public static function veTodas(array $roles): bool
    {
        return array_intersect(self::VEN_TODAS, $roles) !== [];
    }

    /**
     * @param  list<string>  $roles
     */
    public static function puedeVer(LaborAgricola $labor, string $idUsuario, array $roles): bool
    {
        return self::veTodas($roles)
            || (in_array('tecnico_campo', $roles, true)
                && ($labor->estado === EstadoLabor::PROGRAMADA || $labor->esDe($idUsuario)));
    }
}
