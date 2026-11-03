<?php

namespace App\Infrastructure\Http;

use App\Application\Contracts\CampaniaNoDisponible;
use App\Application\Contracts\PasarelaCampania;
use App\Domain\FieldTask\CampaniaConsultada;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Context;
use Illuminate\Support\Facades\Http;

/**
 * GET /api/gestion/v1/campanias/{id}/estado a través del API Gateway, con tiempo límite y un solo intento (README D-12).
 */
final class ClienteServicioGestion implements PasarelaCampania
{
    public function __construct(private readonly TokenCuentaServicio $token) {}

    public function consultar(string $idCampania): ?CampaniaConsultada
    {
        $tiempoLimite = (float) config('servicios.tiempo_limite_gestion_segundos');
        $url = rtrim((string) config('servicios.api_gateway_url'), '/')."/api/gestion/v1/campanias/{$idCampania}/estado";

        try {
            $respuesta = Http::withToken($this->token->obtener())
                ->acceptJson()
                ->withHeaders(['X-Correlation-Id' => (string) Context::get('idCorrelacion', '')])
                ->connectTimeout($tiempoLimite)
                ->timeout($tiempoLimite)
                ->get($url);
        } catch (ConnectionException $e) {
            throw new CampaniaNoDisponible('servicio-gestion no respondió: '.$e->getMessage());
        }

        // Un 404 del Gateway (ruta desconocida) no es "campaña inexistente": solo el código de gestión lo es
        if ($respuesta->status() === 404 && $respuesta->json('codigo') === 'CAMPANIA_NO_ENCONTRADA') {
            return null;
        }
        if (in_array($respuesta->status(), [401, 403], true)) {
            $this->token->olvidar();
        }
        if (! $respuesta->successful()) {
            throw new CampaniaNoDisponible("servicio-gestion respondió HTTP {$respuesta->status()}.");
        }

        $datos = $respuesta->json();
        if (! is_array($datos) || ! is_string($datos['id'] ?? null) || ! is_string($datos['idParcela'] ?? null) || ! is_string($datos['estado'] ?? null)) {
            throw new CampaniaNoDisponible('La respuesta de servicio-gestion no tiene el formato esperado.');
        }

        return new CampaniaConsultada(strtolower($datos['id']), strtolower($datos['idParcela']), $datos['estado']);
    }
}
