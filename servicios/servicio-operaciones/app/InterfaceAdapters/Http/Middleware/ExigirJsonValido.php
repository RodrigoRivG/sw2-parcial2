<?php

namespace App\InterfaceAdapters\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Validation\ValidationException;
use Symfony\Component\HttpFoundation\Response;

/**
 * Laravel ignora un cuerpo JSON mal formado; aquí se rechaza con 400 DATOS_INVALIDOS.
 */
final class ExigirJsonValido
{
    public function handle(Request $request, Closure $next): Response
    {
        $contenido = $request->getContent();
        if ($request->isJson() && trim($contenido) !== '') {
            json_decode($contenido);
            if (json_last_error() !== JSON_ERROR_NONE) {
                throw ValidationException::withMessages(['cuerpo' => 'El cuerpo no es un JSON válido.']);
            }
        }

        return $next($request);
    }
}
