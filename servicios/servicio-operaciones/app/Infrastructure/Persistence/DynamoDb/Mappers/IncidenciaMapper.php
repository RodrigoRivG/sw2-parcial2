<?php

namespace App\Infrastructure\Persistence\DynamoDb\Mappers;

use App\Domain\FieldTask\Responsable;
use App\Domain\Incident\ClasificacionImagen;
use App\Domain\Incident\Incidencia;
use App\Domain\Incident\OrigenClasificacion;
use App\Domain\Incident\ReferenciaFoto;
use App\Domain\Incident\TipoIncidencia;
use App\Infrastructure\Persistence\DynamoDb\FormatoFecha;

/**
 * Incidencia ↔ ítem de la tabla `incidencias` (spec-incidencias.md 2.3).
 */
final class IncidenciaMapper
{
    /**
     * @return array<string, mixed>
     */
    public static function aItem(Incidencia $incidencia): array
    {
        return array_filter([
            'id' => $incidencia->id,
            'tipo' => $incidencia->tipo->value,
            'descripcion' => $incidencia->descripcion,
            'fecha_observacion' => FormatoFecha::conHora($incidencia->fechaObservacion),
            'id_parcela' => $incidencia->idParcela,
            'id_campania' => $incidencia->idCampania,
            'clave_foto' => $incidencia->foto->clave,
            'tipo_contenido_foto' => $incidencia->foto->tipoContenido,
            'tamanio_foto' => $incidencia->foto->tamanio,
            'clasificacion' => $incidencia->clasificacion === null ? null : [
                'categoria' => $incidencia->clasificacion->categoria,
                'confianza' => $incidencia->clasificacion->confianza,
                'version_modelo' => $incidencia->clasificacion->versionModelo,
                'origen' => $incidencia->clasificacion->origen->value,
            ],
            'id_registrador' => $incidencia->registradaPor->id,
            'nombre_registrador' => $incidencia->registradaPor->nombre,
            'fecha_creacion_dispositivo' => FormatoFecha::conHora($incidencia->fechaCreacion),
            'fecha_recepcion' => FormatoFecha::conHora($incidencia->fechaRecepcion),
            'huella' => $incidencia->huella,
            // Índice disperso: solo mientras falta publicar el evento (RQ-INC-08)
            'notificacion_pendiente' => $incidencia->notificacionPendiente ? '1' : null,
            'version' => $incidencia->version,
        ], fn ($valor) => $valor !== null);
    }

    /**
     * @param  array<string, mixed>  $item
     */
    public static function aIncidencia(array $item): Incidencia
    {
        $clasificacion = $item['clasificacion'] ?? null;

        return new Incidencia(
            id: $item['id'],
            tipo: TipoIncidencia::from($item['tipo']),
            descripcion: $item['descripcion'],
            fechaObservacion: FormatoFecha::leerConHora($item['fecha_observacion']),
            idParcela: $item['id_parcela'],
            idCampania: $item['id_campania'] ?? null,
            foto: new ReferenciaFoto($item['clave_foto'], $item['tipo_contenido_foto'], (int) $item['tamanio_foto']),
            clasificacion: $clasificacion === null ? null : ClasificacionImagen::crear(
                $clasificacion['categoria'], $clasificacion['confianza'], $clasificacion['version_modelo'],
                OrigenClasificacion::from($clasificacion['origen']),
            ),
            registradaPor: new Responsable($item['id_registrador'], $item['nombre_registrador']),
            fechaCreacion: FormatoFecha::leerConHora($item['fecha_creacion_dispositivo']),
            fechaRecepcion: FormatoFecha::leerConHora($item['fecha_recepcion']),
            huella: $item['huella'],
            notificacionPendiente: isset($item['notificacion_pendiente']),
            version: (int) $item['version'],
        );
    }
}
