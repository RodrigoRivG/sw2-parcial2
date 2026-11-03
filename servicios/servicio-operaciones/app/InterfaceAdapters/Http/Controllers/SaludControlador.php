<?php

namespace App\InterfaceAdapters\Http\Controllers;

use App\InterfaceAdapters\Http\Salud\ComprobacionSalud;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Log;
use Throwable;

final class SaludControlador
{
    /**
     * @param  iterable<ComprobacionSalud>  $comprobaciones
     */
    public function __construct(private readonly iterable $comprobaciones) {}

    public function liveness(): JsonResponse
    {
        return new JsonResponse(['estado' => 'UP']);
    }

    public function readiness(): JsonResponse
    {
        $componentes = [];
        $todoArriba = true;

        foreach ($this->comprobaciones as $comprobacion) {
            try {
                $comprobacion->comprobar();
                $componentes[$comprobacion->nombre()] = ['estado' => 'UP'];
            } catch (Throwable $e) {
                $todoArriba = false;
                $componentes[$comprobacion->nombre()] = ['estado' => 'DOWN'];
                Log::warning('Readiness: dependencia sin respuesta', ['dependencia' => $comprobacion->nombre(), 'error' => $e->getMessage()]);
            }
        }

        return new JsonResponse(
            ['estado' => $todoArriba ? 'UP' : 'DOWN', 'componentes' => $componentes],
            $todoArriba ? 200 : 503,
        );
    }
}
