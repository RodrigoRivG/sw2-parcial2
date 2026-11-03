<?php

namespace App\Domain\Saga;

/**
 * Respuestas de los participantes (RQ-SAG-09 de inventario y 2.3 de gestión), con el paso al que responden.
 */
enum TipoRespuesta: string
{
    case INSUMOS_DESCONTADOS = 'InsumosDescontados';
    case INSUMOS_RECHAZADOS = 'InsumosRechazados';
    case INSUMOS_RESTAURADOS = 'InsumosRestaurados';
    case COSTO_REGISTRADO = 'CostoCampaniaRegistrado';
    case COSTO_RECHAZADO = 'CostoCampaniaRechazado';
    case COSTO_ANULADO = 'CostoCampaniaAnulado';
    case ANULACION_RECHAZADA = 'AnulacionCostoRechazada';

    public function paso(): PasoSaga
    {
        return match ($this) {
            self::INSUMOS_DESCONTADOS, self::INSUMOS_RECHAZADOS => PasoSaga::DESCONTAR_INSUMOS,
            self::COSTO_REGISTRADO, self::COSTO_RECHAZADO => PasoSaga::REGISTRAR_COSTO,
            self::COSTO_ANULADO, self::ANULACION_RECHAZADA => PasoSaga::ANULAR_COSTO,
            self::INSUMOS_RESTAURADOS => PasoSaga::RESTAURAR_INSUMOS,
        };
    }

    public function esRechazo(): bool
    {
        return in_array($this, [self::INSUMOS_RECHAZADOS, self::COSTO_RECHAZADO, self::ANULACION_RECHAZADA], true);
    }
}
