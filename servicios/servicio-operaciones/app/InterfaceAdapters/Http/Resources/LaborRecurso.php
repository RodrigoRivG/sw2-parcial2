<?php

namespace App\InterfaceAdapters\Http\Resources;

use App\Domain\FieldTask\ConsumoInsumo;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\Responsable;
use DateTimeImmutable;

/**
 * Respuesta de labor (spec-labores.md 2.2).
 */
final class LaborRecurso
{
    /**
     * @return array<string, mixed>
     */
    public static function aArreglo(LaborAgricola $labor): array
    {
        return [
            'id' => $labor->id,
            'tipoLabor' => $labor->tipoLabor->value,
            'idParcela' => $labor->idParcela,
            'idCampania' => $labor->idCampania,
            'estado' => $labor->estado->value,
            'fechaReferencia' => $labor->fechaReferencia(),
            'fechaProgramada' => $labor->fechaProgramada,
            'fechaEjecucion' => self::fecha($labor->fechaEjecucion),
            'fechaCreacion' => self::fecha($labor->fechaCreacion),
            'fechaRecepcion' => self::fecha($labor->fechaRecepcion),
            'fechaRecepcionEjecucion' => self::fecha($labor->fechaRecepcionEjecucion),
            'responsable' => self::responsable($labor->responsable),
            'programadaPor' => $labor->programadaPor === null ? null : self::responsable($labor->programadaPor),
            'observaciones' => $labor->observaciones,
            'insumos' => array_map(fn (ConsumoInsumo $c) => ['idInsumo' => $c->idInsumo, 'cantidad' => $c->cantidad->valor], $labor->insumos),
            'validacionCampania' => $labor->validacionCampania->value,
            'idSaga' => $labor->idSaga,
            'motivo' => $labor->motivo === null ? null : [
                'codigo' => $labor->motivo->codigo,
                'mensaje' => $labor->motivo->mensaje,
                'detalles' => $labor->motivo->detalles,
            ],
            'resolucion' => $labor->resolucion === null ? null : [
                'decision' => $labor->resolucion->decision->value,
                'observacion' => $labor->resolucion->observacion,
                'administrador' => self::responsable($labor->resolucion->administrador),
                'fecha' => self::fecha($labor->resolucion->fecha),
                'motivoAnterior' => $labor->resolucion->motivoAnterior === null ? null : [
                    'codigo' => $labor->resolucion->motivoAnterior->codigo,
                    'mensaje' => $labor->resolucion->motivoAnterior->mensaje,
                    'detalles' => $labor->resolucion->motivoAnterior->detalles,
                ],
            ],
            'idsSagaAnteriores' => $labor->idsSagaAnteriores,
            'version' => $labor->version,
            'fechaActualizacion' => self::fecha($labor->fechaActualizacion),
        ];
    }

    /**
     * @return array{id: string, nombre: string}
     */
    private static function responsable(Responsable $responsable): array
    {
        return ['id' => $responsable->id, 'nombre' => $responsable->nombre];
    }

    private static function fecha(?DateTimeImmutable $fecha): ?string
    {
        return $fecha?->setTimezone(new \DateTimeZone('UTC'))->format('Y-m-d\TH:i:s\Z');
    }
}
