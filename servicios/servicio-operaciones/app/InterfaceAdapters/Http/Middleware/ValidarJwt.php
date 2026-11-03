<?php

namespace App\InterfaceAdapters\Http\Middleware;

use App\Application\Security\UsuarioAutenticado;
use App\InterfaceAdapters\Http\Security\NoAutenticado;
use App\InterfaceAdapters\Http\Security\ProveedorClavesJwt;
use Closure;
use Firebase\JWT\JWT;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;
use Throwable;

/**
 * Valida firma (JWKS), emisor, audiencia y vigencia del token en cada solicitud (constitución §9, RNF-02).
 */
final class ValidarJwt
{
    /** Tolerancia de reloj entre Keycloak y este servicio. */
    private const TOLERANCIA_SEGUNDOS = 30;

    public function __construct(private readonly ProveedorClavesJwt $proveedorClaves) {}

    public function handle(Request $request, Closure $next): Response
    {
        if (preg_match('/^Bearer\s+(\S+)$/i', (string) $request->header('Authorization'), $coincidencia) !== 1) {
            throw new NoAutenticado('Falta el token de acceso.');
        }

        $claims = $this->decodificar($coincidencia[1]);

        if (($claims->iss ?? null) !== config('keycloak.emisor')) {
            throw new NoAutenticado('El emisor del token no es válido.');
        }
        $audiencias = (array) ($claims->aud ?? []);
        if (! in_array(config('keycloak.audiencia'), $audiencias, true)) {
            throw new NoAutenticado('La audiencia del token no es válida.');
        }
        if (! is_string($claims->sub ?? null) || $claims->sub === '') {
            throw new NoAutenticado('El token no identifica al usuario.');
        }

        $roles = array_values(array_filter((array) ($claims->realm_access->roles ?? []), 'is_string'));
        $nombre = $claims->name ?? $claims->preferred_username ?? $claims->sub;

        $request->attributes->set(UsuarioAutenticado::class, new UsuarioAutenticado($claims->sub, (string) $nombre, $roles));

        return $next($request);
    }

    private function decodificar(string $token): object
    {
        JWT::$leeway = self::TOLERANCIA_SEGUNDOS;

        try {
            return JWT::decode($token, $this->proveedorClaves->claves());
        } catch (Throwable $primerError) {
            // Keycloak rotó sus claves: se descargan una vez más
            if (! str_contains($primerError->getMessage(), '"kid"')) {
                throw new NoAutenticado('El token no es válido.');
            }
        }

        try {
            return JWT::decode($token, $this->proveedorClaves->claves(refrescar: true));
        } catch (Throwable) {
            throw new NoAutenticado('El token no es válido.');
        }
    }
}
