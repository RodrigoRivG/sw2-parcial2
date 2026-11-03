<?php

namespace App\InterfaceAdapters\Http\Security;

use Firebase\JWT\Key;

/**
 * Claves públicas con las que se verifica la firma del JWT. Los tests usan una clave local.
 */
interface ProveedorClavesJwt
{
    /**
     * @param  bool  $refrescar  vuelve a descargarlas (por ejemplo, ante un `kid` desconocido)
     * @return array<string, Key> claves indexadas por `kid`
     */
    public function claves(bool $refrescar = false): array;
}
