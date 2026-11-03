<?php

namespace App\Infrastructure\Persistence\DynamoDb\Mappers;

use App\Domain\FieldTask\ConsumoInsumo;
use App\Domain\FieldTask\DecisionRevision;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\Resolucion;
use App\Domain\FieldTask\Responsable;
use App\Domain\FieldTask\TipoLabor;
use App\Domain\FieldTask\ValidacionCampania;
use App\Domain\Shared\Cantidad;
use App\Domain\Shared\Motivo;
use App\Infrastructure\Persistence\DynamoDb\FormatoFecha;
use DateTimeImmutable;

/**
 * LaborAgricola ↔ ítem de la tabla `labores` (spec-labores.md 2.3). Atributos en snake_case; decimales y fechas como texto.
 */
final class LaborMapper
{
    /**
     * @return array<string, mixed> sin atributos nulos (los índices dispersos dependen de su ausencia)
     */
    public static function aItem(LaborAgricola $labor): array
    {
        $item = [
            'id' => $labor->id,
            'tipo_labor' => $labor->tipoLabor->value,
            'id_parcela' => $labor->idParcela,
            'id_campania' => $labor->idCampania,
            'estado' => $labor->estado->value,
            'fecha_programada' => $labor->fechaProgramada,
            'fecha_ejecucion' => self::fecha($labor->fechaEjecucion),
            'fecha_creacion_dispositivo' => self::fecha($labor->fechaCreacion),
            'fecha_recepcion' => self::fecha($labor->fechaRecepcion),
            'fecha_recepcion_ejecucion' => self::fecha($labor->fechaRecepcionEjecucion),
            'fecha_referencia' => $labor->fechaReferencia(),
            'id_responsable' => $labor->responsable->id,
            'nombre_responsable' => $labor->responsable->nombre,
            'id_programada_por' => $labor->programadaPor?->id,
            'nombre_programada_por' => $labor->programadaPor?->nombre,
            'observaciones' => $labor->observaciones,
            'insumos' => array_map(fn (ConsumoInsumo $c) => ['id_insumo' => $c->idInsumo, 'cantidad' => $c->cantidad->valor], $labor->insumos),
            'validacion_campania' => $labor->validacionCampania->value,
            'id_saga' => $labor->idSaga,
            'motivo' => self::motivo($labor->motivo),
            'huella_creacion' => $labor->huellaCreacion,
            'id_operacion_realizacion' => $labor->idOperacionRealizacion,
            'huella_realizacion' => $labor->huellaRealizacion,
            'validacion_pendiente' => $labor->validacionPendiente() ? '1' : null,
            'fecha_proximo_validacion' => self::fecha($labor->fechaProximoValidacion),
            'intentos_validacion' => $labor->intentosValidacion,
            'version' => $labor->version,
            'fecha_actualizacion' => self::fecha($labor->fechaActualizacion),
            'resolucion' => $labor->resolucion === null ? null : array_filter([
                'decision' => $labor->resolucion->decision->value,
                'observacion' => $labor->resolucion->observacion,
                'id_administrador' => $labor->resolucion->administrador->id,
                'nombre_administrador' => $labor->resolucion->administrador->nombre,
                'fecha' => self::fecha($labor->resolucion->fecha),
                'motivo_anterior' => self::motivo($labor->resolucion->motivoAnterior),
            ], fn ($valor) => $valor !== null),
            'ids_saga_anteriores' => $labor->idsSagaAnteriores === [] ? null : $labor->idsSagaAnteriores,
        ];

        return array_filter($item, fn ($valor) => $valor !== null);
    }

    /**
     * @param  array<string, mixed>  $item  ya sin el formato de DynamoDB (Marshaler::unmarshalItem)
     */
    public static function aLabor(array $item): LaborAgricola
    {
        return new LaborAgricola(
            id: $item['id'],
            tipoLabor: TipoLabor::from($item['tipo_labor']),
            idParcela: $item['id_parcela'],
            idCampania: $item['id_campania'],
            estado: EstadoLabor::from($item['estado']),
            fechaProgramada: $item['fecha_programada'] ?? null,
            fechaEjecucion: self::leerFecha($item['fecha_ejecucion'] ?? null),
            fechaCreacion: FormatoFecha::leerConHora($item['fecha_creacion_dispositivo']),
            fechaRecepcion: FormatoFecha::leerConHora($item['fecha_recepcion']),
            fechaRecepcionEjecucion: self::leerFecha($item['fecha_recepcion_ejecucion'] ?? null),
            responsable: new Responsable($item['id_responsable'], $item['nombre_responsable']),
            programadaPor: isset($item['id_programada_por']) ? new Responsable($item['id_programada_por'], $item['nombre_programada_por']) : null,
            observaciones: $item['observaciones'] ?? null,
            insumos: array_map(
                fn (array $i) => new ConsumoInsumo($i['id_insumo'], Cantidad::desdeTexto($i['cantidad'])),
                array_values($item['insumos'] ?? []),
            ),
            validacionCampania: ValidacionCampania::from($item['validacion_campania']),
            idSaga: $item['id_saga'] ?? null,
            motivo: self::leerMotivo($item['motivo'] ?? null),
            huellaCreacion: $item['huella_creacion'],
            idOperacionRealizacion: $item['id_operacion_realizacion'] ?? null,
            huellaRealizacion: $item['huella_realizacion'] ?? null,
            intentosValidacion: (int) ($item['intentos_validacion'] ?? 0),
            fechaProximoValidacion: self::leerFecha($item['fecha_proximo_validacion'] ?? null),
            version: (int) $item['version'],
            fechaActualizacion: FormatoFecha::leerConHora($item['fecha_actualizacion']),
            resolucion: isset($item['resolucion']) ? new Resolucion(
                DecisionRevision::from($item['resolucion']['decision']),
                $item['resolucion']['observacion'],
                new Responsable($item['resolucion']['id_administrador'], $item['resolucion']['nombre_administrador']),
                FormatoFecha::leerConHora($item['resolucion']['fecha']),
                self::leerMotivo($item['resolucion']['motivo_anterior'] ?? null),
            ) : null,
            idsSagaAnteriores: array_values($item['ids_saga_anteriores'] ?? []),
        );
    }

    /**
     * @return array{codigo: string, mensaje: string, detalles: list<array<string, mixed>>}|null
     */
    private static function motivo(?Motivo $motivo): ?array
    {
        return $motivo === null ? null : ['codigo' => $motivo->codigo, 'mensaje' => $motivo->mensaje, 'detalles' => $motivo->detalles];
    }

    /**
     * @param  array<string, mixed>|null  $motivo
     */
    private static function leerMotivo(?array $motivo): ?Motivo
    {
        return $motivo === null ? null : new Motivo($motivo['codigo'], $motivo['mensaje'], array_values($motivo['detalles'] ?? []));
    }

    private static function fecha(?DateTimeImmutable $fecha): ?string
    {
        return $fecha === null ? null : FormatoFecha::conHora($fecha);
    }

    private static function leerFecha(?string $texto): ?DateTimeImmutable
    {
        return $texto === null ? null : FormatoFecha::leerConHora($texto);
    }
}
