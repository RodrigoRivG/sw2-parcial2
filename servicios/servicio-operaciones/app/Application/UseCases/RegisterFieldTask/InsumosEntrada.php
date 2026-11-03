<?php

namespace App\Application\UseCases\RegisterFieldTask;

use App\Domain\FieldTask\ConsumoInsumo;
use App\Domain\Shared\Cantidad;

/**
 * Convierte los insumos recibidos y los normaliza para la huella (cantidades con escala 3, ordenados por insumo).
 */
final class InsumosEntrada
{
    /**
     * @param  list<array{idInsumo: string, cantidad: string}>  $insumos
     * @return list<ConsumoInsumo>
     */
    public static function aConsumos(array $insumos): array
    {
        return array_map(
            fn (array $insumo) => new ConsumoInsumo(strtolower($insumo['idInsumo']), Cantidad::desdeTexto($insumo['cantidad'])),
            $insumos,
        );
    }

    /**
     * @param  list<ConsumoInsumo>  $consumos
     * @return list<array{idInsumo: string, cantidad: string}>
     */
    public static function paraHuella(array $consumos): array
    {
        $normalizados = array_map(fn (ConsumoInsumo $c) => ['idInsumo' => $c->idInsumo, 'cantidad' => $c->cantidad->valor], $consumos);
        usort($normalizados, fn (array $a, array $b) => $a['idInsumo'] <=> $b['idInsumo']);

        return $normalizados;
    }
}
