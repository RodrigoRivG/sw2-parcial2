<?php

namespace App\InterfaceAdapters\Http;

use App\Application\Contracts\CursorInvalido;
use App\Application\Security\SinPermiso;
use App\Domain\Shared\ExcepcionDominio;
use App\Domain\Shared\TipoErrorDominio;
use App\InterfaceAdapters\Http\Security\NoAutenticado;
use Illuminate\Http\Exceptions\PostTooLargeException;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Context;
use Illuminate\Validation\ValidationException;
use Symfony\Component\HttpKernel\Exception\HttpExceptionInterface;
use Symfony\Component\HttpKernel\Exception\MethodNotAllowedHttpException;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;
use Throwable;

/**
 * Formato común de error de la constitución §11. El error completo de un 500 lo registra el handler de Laravel.
 */
final class RenderizadorErrores
{
    public static function renderizar(Throwable $e): JsonResponse
    {
        [$estado, $codigo, $mensaje, $detalles] = match (true) {
            $e instanceof ValidationException => [400, 'DATOS_INVALIDOS', 'Los datos enviados no son válidos.', self::detallesValidacion($e)],
            $e instanceof CursorInvalido => [400, 'DATOS_INVALIDOS', $e->getMessage(), [['campo' => 'cursor', 'mensaje' => $e->getMessage()]]],
            $e instanceof PostTooLargeException => [400, 'DATOS_INVALIDOS', 'La solicitud supera el tamaño máximo permitido.', []],
            $e instanceof NoAutenticado => [401, 'NO_AUTENTICADO', $e->getMessage(), []],
            $e instanceof SinPermiso => [403, 'SIN_PERMISO', $e->getMessage(), []],
            $e instanceof ExcepcionDominio => [self::estadoDominio($e->tipo), $e->codigo, $e->getMessage(), $e->detalles],
            $e instanceof NotFoundHttpException => [404, 'RECURSO_NO_ENCONTRADO', 'El recurso solicitado no existe.', []],
            $e instanceof MethodNotAllowedHttpException => [405, 'METODO_NO_PERMITIDO', 'El método no está permitido en esta ruta.', []],
            $e instanceof HttpExceptionInterface && $e->getStatusCode() < 500 => [400, 'DATOS_INVALIDOS', 'La solicitud no es válida.', []],
            default => [500, 'ERROR_INTERNO', 'Ocurrió un error inesperado. Intente nuevamente.', []],
        };

        return self::respuesta($estado, $codigo, $mensaje, $detalles);
    }

    /**
     * @param  list<array<string, mixed>>  $detalles
     */
    public static function respuesta(int $estado, string $codigo, string $mensaje, array $detalles = []): JsonResponse
    {
        return new JsonResponse([
            'codigo' => $codigo,
            'mensaje' => $mensaje,
            'detalles' => $detalles,
            'idCorrelacion' => (string) Context::get('idCorrelacion', ''),
        ], $estado);
    }

    private static function estadoDominio(TipoErrorDominio $tipo): int
    {
        return match ($tipo) {
            TipoErrorDominio::NO_ENCONTRADO => 404,
            TipoErrorDominio::CONFLICTO => 409,
            TipoErrorDominio::REGLA_NEGOCIO => 422,
        };
    }

    /**
     * @return list<array{campo: string, mensaje: string}>
     */
    private static function detallesValidacion(ValidationException $e): array
    {
        $detalles = [];
        foreach ($e->errors() as $campo => $mensajes) {
            foreach ($mensajes as $mensaje) {
                $detalles[] = ['campo' => (string) $campo, 'mensaje' => $mensaje];
            }
        }

        return $detalles;
    }
}
