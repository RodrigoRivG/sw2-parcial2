<?php

namespace Tests\Support;

use App\InterfaceAdapters\Http\Security\ProveedorClavesJwt;
use Firebase\JWT\JWT;
use Firebase\JWT\Key;

/**
 * Par RSA de la corrida de tests: firma tokens propios y hace de JWKS, sin Keycloak (spec-labores.md 2.1).
 */
final class Tokens implements ProveedorClavesJwt
{
    public const KID = 'clave-pruebas';

    private static ?string $privada = null;

    private static ?string $publica = null;

    /**
     * @param  list<string>  $roles
     * @param  array<string, mixed>  $cambios  claims que se reemplazan o agregan (null quita el claim)
     */
    public static function para(array $roles, string $sub = 'usuario-pruebas', array $cambios = [], ?string $clavePrivada = null): string
    {
        $ahora = time();
        $claims = array_merge([
            'iss' => config('keycloak.emisor'),
            'aud' => ['account', config('keycloak.audiencia')],
            'sub' => $sub,
            'name' => 'Usuario '.$sub,
            'preferred_username' => $sub,
            'iat' => $ahora,
            'exp' => $ahora + 300,
            'realm_access' => ['roles' => $roles],
        ], $cambios);
        $claims = array_filter($claims, fn ($valor) => $valor !== null);

        return JWT::encode($claims, $clavePrivada ?? self::privada(), 'RS256', self::KID);
    }

    /** Clave privada distinta, para probar firmas inválidas. */
    public static function otraClavePrivada(): string
    {
        $par = openssl_pkey_new(['private_key_bits' => 2048, 'private_key_type' => OPENSSL_KEYTYPE_RSA]);
        openssl_pkey_export($par, $pem);

        return $pem;
    }

    public function claves(bool $refrescar = false): array
    {
        self::privada();

        return [self::KID => new Key((string) self::$publica, 'RS256')];
    }

    private static function privada(): string
    {
        if (self::$privada === null) {
            $par = openssl_pkey_new(['private_key_bits' => 2048, 'private_key_type' => OPENSSL_KEYTYPE_RSA]);
            openssl_pkey_export($par, $privada);
            self::$privada = $privada;
            self::$publica = openssl_pkey_get_details($par)['key'];
        }

        return self::$privada;
    }
}
