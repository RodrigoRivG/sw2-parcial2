<?php

namespace App\InterfaceAdapters\Http\Resources;

use App\Application\UseCases\QueryIncidents\IncidenciaConFoto;
use App\Domain\Incident\Incidencia;
use DateTimeImmutable;
use DateTimeZone;

/**
 * Respuesta de incidencia (spec-incidencias.md 2.2). La foto siempre como URL prefirmada, nunca la clave ni una URL pública.
 */
final class IncidenciaRecurso
{
    /**
     * @return array<string, mixed>
     */
    public static function aArreglo(IncidenciaConFoto $conFoto): array
    {
        $incidencia = $conFoto->incidencia;

        return [
            'id' => $incidencia->id,
            'tipo' => $incidencia->tipo->value,
            'descripcion' => $incidencia->descripcion,
            'fechaObservacion' => self::fecha($incidencia->fechaObservacion),
            'idParcela' => $incidencia->idParcela,
            'idCampania' => $incidencia->idCampania,
            'foto' => [
                'url' => $conFoto->foto->url,
                'tipoContenido' => $incidencia->foto->tipoContenido,
                'tamanio' => $incidencia->foto->tamanio,
                'expiraEn' => self::fecha($conFoto->foto->expiraEn),
            ],
            'clasificacion' => self::clasificacion($incidencia),
            'registradaPor' => ['id' => $incidencia->registradaPor->id, 'nombre' => $incidencia->registradaPor->nombre],
            'fechaCreacion' => self::fecha($incidencia->fechaCreacion),
            'fechaRecepcion' => self::fecha($incidencia->fechaRecepcion),
        ];
    }

    /**
     * @return array<string, mixed>|null
     */
    private static function clasificacion(Incidencia $incidencia): ?array
    {
        if ($incidencia->clasificacion === null) {
            return null;
        }

        return [
            'categoria' => $incidencia->clasificacion->categoria,
            'confianza' => $incidencia->clasificacion->confianza,
            'versionModelo' => $incidencia->clasificacion->versionModelo,
            'origen' => $incidencia->clasificacion->origen->value,
            // RN-13: los resultados de IA son orientativos
            'orientativa' => true,
        ];
    }

    private static function fecha(DateTimeImmutable $fecha): string
    {
        return $fecha->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:s\Z');
    }
}
