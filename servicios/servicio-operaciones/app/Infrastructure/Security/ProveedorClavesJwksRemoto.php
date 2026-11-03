<?php

namespace App\Infrastructure\Security;

use App\InterfaceAdapters\Http\Security\ProveedorClavesJwt;
use Firebase\JWT\JWK;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;

/**
 * Descarga el JWKS de Keycloak por la red interna y lo guarda 10 minutos (spec-labores.md 2.1).
 */
final class ProveedorClavesJwksRemoto implements ProveedorClavesJwt
{
    private const CLAVE_CACHE = 'keycloak.jwks';

    private const SEGUNDOS_CACHE = 600;

    public function claves(bool $refrescar = false): array
    {
        if ($refrescar) {
            Cache::forget(self::CLAVE_CACHE);
        }

        $jwks = Cache::remember(self::CLAVE_CACHE, self::SEGUNDOS_CACHE, function () {
            $respuesta = Http::timeout(3)->get((string) config('keycloak.jwks_uri'))->throw()->json();
            // Keycloak publica también una clave de cifrado (use = enc) que no sirve para verificar firmas
            $respuesta['keys'] = array_values(array_filter(
                $respuesta['keys'] ?? [],
                fn (array $clave) => ($clave['use'] ?? 'sig') === 'sig',
            ));

            return $respuesta;
        });

        return JWK::parseKeySet($jwks, 'RS256');
    }
}
