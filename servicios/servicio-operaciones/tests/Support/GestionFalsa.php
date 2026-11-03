<?php

namespace Tests\Support;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;

/**
 * servicio-gestion (a través del Gateway) y el token de Keycloak simulados con Http::fake (spec-labores.md 2.1).
 * El estado es mutable para pasar de "caído" a "disponible" dentro de un mismo test.
 */
final class GestionFalsa
{
    /** @var array<string, array{idParcela: string, estado: string}> */
    private static array $campanias = [];

    private static bool $disponible = true;

    private static int $consultas = 0;

    /** Si no es null, el Gateway responde este código HTTP (5xx, 401, 403…). */
    private static ?int $estadoError = null;

    public static function instalar(): void
    {
        self::$campanias = [];
        self::$disponible = true;
        self::$consultas = 0;
        self::$estadoError = null;

        Http::fake([
            config('keycloak.token_url') => Http::response(['access_token' => 'token-servicio', 'expires_in' => 300]),
            rtrim((string) config('servicios.api_gateway_url'), '/').'/api/gestion/v1/campanias/*' => function (Request $request) {
                self::$consultas++;
                if (! self::$disponible) {
                    throw new ConnectionException('cURL error 28: Operation timed out');
                }
                if (self::$estadoError !== null) {
                    return Http::response(['codigo' => 'ERROR'], self::$estadoError);
                }
                preg_match('#/campanias/([^/]+)/estado$#', $request->url(), $coincidencia);
                $id = $coincidencia[1] ?? '';
                if (! isset(self::$campanias[$id])) {
                    return Http::response(['codigo' => 'CAMPANIA_NO_ENCONTRADA', 'mensaje' => 'La campaña no existe.'], 404);
                }

                return Http::response([
                    'id' => $id,
                    'idParcela' => self::$campanias[$id]['idParcela'],
                    'idCultivo' => '5b1d4f0e-0000-4000-8000-000000000001',
                    'estado' => self::$campanias[$id]['estado'],
                    'fechaInicio' => '2026-11-01',
                    'fechaFin' => '2027-03-30',
                ]);
            },
        ]);
    }

    public static function campania(string $id, string $idParcela, string $estado = 'EN_CURSO'): void
    {
        self::$campanias[$id] = ['idParcela' => $idParcela, 'estado' => $estado];
    }

    public static function disponible(bool $disponible): void
    {
        self::$disponible = $disponible;
    }

    public static function responderError(?int $estado): void
    {
        self::$estadoError = $estado;
    }

    public static function consultas(): int
    {
        return self::$consultas;
    }
}
