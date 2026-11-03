<?php

namespace App\InterfaceAdapters\Http\Controllers;

use Illuminate\Http\Response;

/**
 * Sirve el contrato OpenAPI escrito a mano (constitución §7, README D-15).
 */
final class OpenApiControlador
{
    public function __invoke(): Response
    {
        return new Response((string) file_get_contents(base_path('openapi.yaml')), 200, [
            'Content-Type' => 'application/yaml; charset=utf-8',
        ]);
    }
}
