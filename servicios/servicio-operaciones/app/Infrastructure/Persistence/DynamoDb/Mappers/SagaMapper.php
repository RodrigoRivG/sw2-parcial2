<?php

namespace App\Infrastructure\Persistence\DynamoDb\Mappers;

use App\Domain\FieldTask\ConsumoInsumo;
use App\Domain\Saga\EstadoPaso;
use App\Domain\Saga\EstadoSaga;
use App\Domain\Saga\PasoSaga;
use App\Domain\Saga\RegistroPaso;
use App\Domain\Saga\Saga;
use App\Domain\Shared\Cantidad;
use App\Infrastructure\Persistence\DynamoDb\FormatoFecha;
use DateTimeImmutable;

/**
 * Saga ↔ ítem de la tabla `sagas` (spec-saga.md 2.6).
 */
final class SagaMapper
{
    /**
     * @return array<string, mixed>
     */
    public static function aItem(Saga $saga): array
    {
        $pasos = [];
        foreach ($saga->pasos as $nombre => $paso) {
            $pasos[$nombre] = array_filter([
                'estado' => $paso->estado->value,
                'intentos' => $paso->intentos,
                'fecha_primer_envio' => self::fecha($paso->fechaPrimerEnvio),
                'fecha_ultimo_envio' => self::fecha($paso->fechaUltimoEnvio),
                'fecha_respuesta' => self::fecha($paso->fechaRespuesta),
                'respuesta' => $paso->respuesta === null ? null : array_filter($paso->respuesta, fn ($v) => $v !== null),
                'error' => $paso->error,
            ], fn ($valor) => $valor !== null);
        }

        return array_filter([
            'id_saga' => $saga->idSaga,
            'id_labor' => $saga->idLabor,
            'id_campania' => $saga->idCampania,
            'items' => array_map(fn (ConsumoInsumo $c) => ['id_insumo' => $c->idInsumo, 'cantidad' => $c->cantidad->valor], $saga->items),
            'estado' => $saga->estado->value,
            'paso_actual' => $saga->pasoActual->value,
            'costo_total' => $saga->costoTotal,
            'pasos' => $pasos,
            'respuestas_tardias' => array_map(fn (array $r) => array_filter([
                'tipo' => $r['tipo'],
                'id_mensaje' => $r['idMensaje'],
                'codigo' => $r['codigo'],
                'fecha_recepcion' => $r['fechaRecepcion'],
            ], fn ($v) => $v !== null), $saga->respuestasTardias),
            // Índice disperso: solo las Sagas activas lo tienen (spec-saga.md 2.6)
            'activa' => $saga->estado->activa() ? '1' : null,
            'fecha_limite' => FormatoFecha::conHora($saga->fechaLimite),
            'version' => $saga->version,
            'fecha_creacion' => FormatoFecha::conHora($saga->fechaCreacion),
            'fecha_actualizacion' => FormatoFecha::conHora($saga->fechaActualizacion),
        ], fn ($valor) => $valor !== null);
    }

    /**
     * @param  array<string, mixed>  $item
     */
    public static function aSaga(array $item): Saga
    {
        $pasos = [];
        foreach ($item['pasos'] as $nombre => $paso) {
            $pasos[$nombre] = new RegistroPaso(
                EstadoPaso::from($paso['estado']),
                (int) $paso['intentos'],
                self::leer($paso['fecha_primer_envio'] ?? null),
                self::leer($paso['fecha_ultimo_envio'] ?? null),
                self::leer($paso['fecha_respuesta'] ?? null),
                isset($paso['respuesta']) ? [
                    'tipo' => $paso['respuesta']['tipo'],
                    'codigo' => $paso['respuesta']['codigo'] ?? null,
                    'motivo' => $paso['respuesta']['motivo'] ?? null,
                ] : null,
                $paso['error'] ?? null,
            );
        }

        return new Saga(
            idSaga: $item['id_saga'],
            idLabor: $item['id_labor'],
            idCampania: $item['id_campania'],
            items: array_map(fn (array $i) => new ConsumoInsumo($i['id_insumo'], Cantidad::desdeTexto($i['cantidad'])), array_values($item['items'] ?? [])),
            estado: EstadoSaga::from($item['estado']),
            pasoActual: PasoSaga::from($item['paso_actual']),
            costoTotal: $item['costo_total'] ?? null,
            pasos: $pasos,
            respuestasTardias: array_map(fn (array $r) => [
                'tipo' => $r['tipo'],
                'idMensaje' => $r['id_mensaje'],
                'codigo' => $r['codigo'] ?? null,
                'fechaRecepcion' => $r['fecha_recepcion'],
            ], array_values($item['respuestas_tardias'] ?? [])),
            fechaLimite: FormatoFecha::leerConHora($item['fecha_limite']),
            version: (int) $item['version'],
            fechaCreacion: FormatoFecha::leerConHora($item['fecha_creacion']),
            fechaActualizacion: FormatoFecha::leerConHora($item['fecha_actualizacion']),
        );
    }

    private static function fecha(?DateTimeImmutable $fecha): ?string
    {
        return $fecha === null ? null : FormatoFecha::conHora($fecha);
    }

    private static function leer(?string $texto): ?DateTimeImmutable
    {
        return $texto === null ? null : FormatoFecha::leerConHora($texto);
    }
}
