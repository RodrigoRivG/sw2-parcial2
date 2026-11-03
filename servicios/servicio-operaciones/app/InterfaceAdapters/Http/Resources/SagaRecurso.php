<?php

namespace App\InterfaceAdapters\Http\Resources;

use App\Domain\FieldTask\ConsumoInsumo;
use App\Domain\Saga\RegistroPaso;
use App\Domain\Saga\Saga;
use DateTimeImmutable;

/**
 * Respuesta de GET /sagas/{id} (spec-saga.md RQ-SAG-11 y RQ-SAG-12).
 */
final class SagaRecurso
{
    /**
     * @return array<string, mixed>
     */
    public static function aArreglo(Saga $saga): array
    {
        $pasos = [];
        foreach ($saga->pasos as $nombre => $paso) {
            $pasos[] = ['paso' => $nombre, ...self::paso($paso)];
        }

        return [
            'idSaga' => $saga->idSaga,
            'idLabor' => $saga->idLabor,
            'idCampania' => $saga->idCampania,
            'estado' => $saga->estado->value,
            'pasoActual' => $saga->pasoActual->value,
            'costoTotal' => $saga->costoTotal,
            'items' => array_map(fn (ConsumoInsumo $c) => ['idInsumo' => $c->idInsumo, 'cantidad' => $c->cantidad->valor], $saga->items),
            'pasos' => $pasos,
            'respuestasTardias' => $saga->respuestasTardias,
            'fechaLimite' => $saga->estado->activa() ? self::fecha($saga->fechaLimite) : null,
            'version' => $saga->version,
            'fechaCreacion' => self::fecha($saga->fechaCreacion),
            'fechaActualizacion' => self::fecha($saga->fechaActualizacion),
        ];
    }

    /**
     * @return array<string, mixed>
     */
    private static function paso(RegistroPaso $paso): array
    {
        return [
            'estado' => $paso->estado->value,
            'intentos' => $paso->intentos,
            'fechaPrimerEnvio' => self::fecha($paso->fechaPrimerEnvio),
            'fechaUltimoEnvio' => self::fecha($paso->fechaUltimoEnvio),
            'fechaRespuesta' => self::fecha($paso->fechaRespuesta),
            'respuesta' => $paso->respuesta,
            'error' => $paso->error,
        ];
    }

    private static function fecha(?DateTimeImmutable $fecha): ?string
    {
        return $fecha?->setTimezone(new \DateTimeZone('UTC'))->format('Y-m-d\TH:i:s\Z');
    }
}
