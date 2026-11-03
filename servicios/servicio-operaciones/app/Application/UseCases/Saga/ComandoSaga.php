<?php

namespace App\Application\UseCases\Saga;

use App\Domain\FieldTask\ConsumoInsumo;
use App\Domain\Saga\Participante;
use App\Domain\Saga\PasoSaga;
use App\Domain\Saga\Saga;

/**
 * Comando de un paso, con los `datos` exactos que esperan los participantes (spec-saga.md RQ-SAG-02).
 */
final class ComandoSaga
{
    /**
     * @param  array<string, mixed>  $datos
     */
    private function __construct(
        public readonly Participante $destino,
        public readonly string $tipo,
        public readonly array $datos,
    ) {}

    public static function para(Saga $saga, PasoSaga $paso): self
    {
        $base = ['idSaga' => $saga->idSaga, 'idLabor' => $saga->idLabor];

        return match ($paso) {
            PasoSaga::DESCONTAR_INSUMOS => new self($paso->participante(), 'DescontarInsumos', [
                ...$base,
                'items' => array_map(fn (ConsumoInsumo $c) => ['idInsumo' => $c->idInsumo, 'cantidad' => $c->cantidad->valor], $saga->items),
            ]),
            PasoSaga::RESTAURAR_INSUMOS => new self($paso->participante(), 'RestaurarInsumos', $base),
            PasoSaga::REGISTRAR_COSTO => new self($paso->participante(), 'RegistrarCostoCampania', [
                ...$base,
                'idCampania' => $saga->idCampania,
                'monto' => $saga->costoTotal,
                'categoria' => 'INSUMO',
            ]),
            PasoSaga::ANULAR_COSTO => new self($paso->participante(), 'AnularCostoCampania', [...$base, 'idCampania' => $saga->idCampania]),
        };
    }
}
