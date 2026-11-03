<?php

namespace App\InterfaceAdapters\Http\Middleware;

use App\Application\Security\SinPermiso;
use App\Application\Security\UsuarioAutenticado;
use App\InterfaceAdapters\Http\Security\NoAutenticado;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/**
 * `rol:administrador,gerencia`: deja pasar si el usuario tiene al menos uno de los roles.
 */
final class RequerirRol
{
    public function handle(Request $request, Closure $next, string ...$roles): Response
    {
        $usuario = $request->attributes->get(UsuarioAutenticado::class);
        if (! $usuario instanceof UsuarioAutenticado) {
            throw new NoAutenticado;
        }
        if (! $usuario->tieneRol(...$roles)) {
            throw new SinPermiso;
        }

        return $next($request);
    }
}
