<?php

namespace App\Application\UseCases\Saga;

use App\Domain\Saga\RespuestaSaga;
use App\Domain\Saga\TipoRespuesta;

/**
 * Valida los `datos` de cada respuesta según el contrato del participante y los traduce a RespuestaSaga.
 * Reemplaza a los siete manejadores de la lista de referencia de la constitución: cada uno solo leía campos.
 */
final class LectorRespuesta
{
    /**
     * @param  array<string, mixed>  $datos
     */
    public static function leer(TipoRespuesta $tipo, string $idMensaje, array $datos): RespuestaSaga
    {
        self::exigirTexto($datos, 'idSaga');
        self::exigirTexto($datos, 'idLabor');

        return match ($tipo) {
            TipoRespuesta::INSUMOS_DESCONTADOS => new RespuestaSaga($tipo, $idMensaje, costoTotal: self::monto($datos, 'costoTotal')),
            TipoRespuesta::INSUMOS_RECHAZADOS => new RespuestaSaga(
                $tipo, $idMensaje,
                codigo: self::exigirTexto($datos, 'codigo'),
                motivo: self::exigirTexto($datos, 'motivo'),
                detalles: self::lista($datos, 'insumosAfectados'),
            ),
            TipoRespuesta::COSTO_RECHAZADO, TipoRespuesta::ANULACION_RECHAZADA => new RespuestaSaga(
                $tipo, $idMensaje,
                codigo: self::exigirTexto($datos, 'codigo'),
                motivo: self::exigirTexto($datos, 'motivo'),
            ),
            TipoRespuesta::INSUMOS_RESTAURADOS, TipoRespuesta::COSTO_ANULADO => self::conSinEfecto($tipo, $idMensaje, $datos),
            TipoRespuesta::COSTO_REGISTRADO => new RespuestaSaga($tipo, $idMensaje),
        };
    }

    /**
     * @param  array<string, mixed>  $datos
     */
    private static function conSinEfecto(TipoRespuesta $tipo, string $idMensaje, array $datos): RespuestaSaga
    {
        if (! is_bool($datos['sinEfecto'] ?? null)) {
            throw new RespuestaInvalida("{$tipo->value} sin sinEfecto booleano.");
        }

        return new RespuestaSaga($tipo, $idMensaje);
    }

    /**
     * @param  array<string, mixed>  $datos
     */
    private static function exigirTexto(array $datos, string $campo): string
    {
        $valor = $datos[$campo] ?? null;
        if (! is_string($valor) || $valor === '') {
            throw new RespuestaInvalida("Falta el campo {$campo}.");
        }

        return $valor;
    }

    /**
     * Decimal como texto con 2 decimales, nunca número JSON (README D-03).
     *
     * @param  array<string, mixed>  $datos
     */
    private static function monto(array $datos, string $campo): string
    {
        $valor = $datos[$campo] ?? null;
        if (! is_string($valor) || preg_match('/^\d{1,12}\.\d{2}$/', $valor) !== 1) {
            throw new RespuestaInvalida("{$campo} debe ser texto decimal con 2 decimales.");
        }

        return $valor;
    }

    /**
     * @param  array<string, mixed>  $datos
     * @return list<array<string, mixed>>
     */
    private static function lista(array $datos, string $campo): array
    {
        $valor = $datos[$campo] ?? [];
        if (! is_array($valor) || ! array_is_list($valor)) {
            throw new RespuestaInvalida("{$campo} debe ser una lista.");
        }

        return array_values(array_filter($valor, 'is_array'));
    }
}
