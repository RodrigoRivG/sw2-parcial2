<?php

namespace App\Domain\Saga;

enum PasoSaga: string
{
    case DESCONTAR_INSUMOS = 'DESCONTAR_INSUMOS';
    case REGISTRAR_COSTO = 'REGISTRAR_COSTO';
    case ANULAR_COSTO = 'ANULAR_COSTO';
    case RESTAURAR_INSUMOS = 'RESTAURAR_INSUMOS';

    public function participante(): Participante
    {
        return match ($this) {
            self::DESCONTAR_INSUMOS, self::RESTAURAR_INSUMOS => Participante::INVENTARIO,
            self::REGISTRAR_COSTO, self::ANULAR_COSTO => Participante::GESTION,
        };
    }

    /** Las compensaciones se reenvían sin límite; los pasos hacia adelante, hasta el máximo (RQ-SAG-05). */
    public function esCompensacion(): bool
    {
        return $this === self::ANULAR_COSTO || $this === self::RESTAURAR_INSUMOS;
    }
}
