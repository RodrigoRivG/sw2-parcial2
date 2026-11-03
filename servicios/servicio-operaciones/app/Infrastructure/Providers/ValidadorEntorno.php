<?php

namespace App\Infrastructure\Providers;

use RuntimeException;

/**
 * Verifica al arrancar que estén las variables obligatorias (README D-16). Si falta una, el proceso no inicia.
 */
final class ValidadorEntorno
{
    private const OBLIGATORIAS = [
        'AWS_DEFAULT_REGION',
        'API_GATEWAY_URL',
        'KEYCLOAK_ISSUER',
        'KEYCLOAK_JWKS_URI',
        'KEYCLOAK_AUDIENCE',
        'KEYCLOAK_TOKEN_URL',
        'KEYCLOAK_CLIENT_ID',
    ];

    /** @var list<string> */
    private static array $adicionales = [];

    /** Las specs que agregan infraestructura (RabbitMQ, S3) suman aquí sus variables. */
    public static function exigir(string ...$variables): void
    {
        self::$adicionales = array_values(array_unique([...self::$adicionales, ...$variables]));
    }

    public static function validar(): void
    {
        $faltantes = array_values(array_filter(
            [...self::OBLIGATORIAS, ...self::$adicionales],
            fn (string $variable) => in_array(env($variable), [null, ''], true),
        ));

        if ($faltantes !== []) {
            throw new RuntimeException('Faltan variables de entorno obligatorias: '.implode(', ', $faltantes));
        }
    }
}
