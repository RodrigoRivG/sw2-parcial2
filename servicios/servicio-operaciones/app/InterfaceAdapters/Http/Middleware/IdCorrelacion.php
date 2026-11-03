<?php

namespace App\InterfaceAdapters\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Context;
use Illuminate\Support\Str;
use Symfony\Component\HttpFoundation\Response;

/**
 * Toma el X-Correlation-Id del Gateway o genera uno, lo deja en el Context (logs y mensajes)
 * y lo devuelve en la respuesta, también en los errores (constitución §11).
 */
final class IdCorrelacion
{
    public const HEADER = 'X-Correlation-Id';

    public function handle(Request $request, Closure $next): Response
    {
        $recibido = (string) $request->header(self::HEADER);
        $id = preg_match('/^[A-Za-z0-9._-]{1,100}$/', $recibido) === 1 ? $recibido : (string) Str::uuid();

        Context::add('idCorrelacion', $id);

        $respuesta = $next($request);
        $respuesta->headers->set(self::HEADER, $id);

        return $respuesta;
    }
}
