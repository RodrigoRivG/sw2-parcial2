<?php

namespace App\Infrastructure\Http;

use App\Application\Contracts\CampaniaNoDisponible;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;

/**
 * Token de la cuenta de servicio (client credentials), en caché hasta 30 s antes de vencer (README D-12).
 */
final class TokenCuentaServicio
{
    private const CLAVE_CACHE = 'keycloak.token_servicio';

    private const MARGEN_SEGUNDOS = 30;

    public function obtener(): string
    {
        $token = Cache::get(self::CLAVE_CACHE);
        if (is_string($token)) {
            return $token;
        }

        try {
            $respuesta = Http::asForm()
                ->timeout((float) config('servicios.tiempo_limite_gestion_segundos'))
                ->post((string) config('keycloak.token_url'), [
                    'grant_type' => 'client_credentials',
                    'client_id' => config('keycloak.client_id'),
                    'client_secret' => config('keycloak.client_secret'),
                ]);
        } catch (ConnectionException $e) {
            throw new CampaniaNoDisponible('Keycloak no respondió al pedir el token de servicio: '.$e->getMessage());
        }

        $token = $respuesta->json('access_token');
        if (! $respuesta->successful() || ! is_string($token)) {
            throw new CampaniaNoDisponible("Keycloak rechazó el token de servicio (HTTP {$respuesta->status()}).");
        }

        $segundos = max(1, (int) $respuesta->json('expires_in', 60) - self::MARGEN_SEGUNDOS);
        Cache::put(self::CLAVE_CACHE, $token, $segundos);

        return $token;
    }

    public function olvidar(): void
    {
        Cache::forget(self::CLAVE_CACHE);
    }
}
