<?php

namespace App\InterfaceAdapters\Http\Controllers;

use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\SyncOfflineOperations\ResultadoOperacion;
use App\Application\UseCases\SyncOfflineOperations\SincronizarOperacionesCasoUso;
use App\Domain\Shared\ResultadoSincronizacion;
use App\InterfaceAdapters\Http\Requests\SincronizacionRequest;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Context;

final class SincronizacionControlador
{
    public function sincronizar(SincronizacionRequest $request, SincronizarOperacionesCasoUso $sincronizar): JsonResponse
    {
        $resultados = $sincronizar->ejecutar(
            $request->operaciones(),
            $request->attributes->get(UsuarioAutenticado::class),
            (string) Context::get('idCorrelacion', ''),
        );
        $sincronizadas = count(array_filter($resultados, fn (ResultadoOperacion $r) => $r->resultado === ResultadoSincronizacion::SINCRONIZADA));

        return new JsonResponse([
            'resultados' => array_map(self::resultado(...), $resultados),
            'resumen' => ['sincronizadas' => $sincronizadas, 'errores' => count($resultados) - $sincronizadas],
        ]);
    }

    /**
     * @return array<string, mixed> los campos de RQ-SIN-06 que corresponden al resultado
     */
    private static function resultado(ResultadoOperacion $r): array
    {
        $base = ['idOperacion' => $r->idOperacion, 'tipo' => $r->tipo, 'resultado' => $r->resultado->value];

        return $r->resultado === ResultadoSincronizacion::SINCRONIZADA
            ? [...$base, 'repetida' => $r->repetida, 'idRecurso' => $r->idRecurso, 'estado' => $r->estado]
            : [...$base, 'codigo' => $r->codigo, 'mensaje' => $r->mensaje, 'detalles' => $r->detalles, 'reintentable' => $r->reintentable];
    }
}
