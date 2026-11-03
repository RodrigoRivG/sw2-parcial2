<?php

namespace App\Application\UseCases\RegisterIncident;

use App\Application\Contracts\PublicacionFallida;
use App\Application\Contracts\PublicadorMensajes;
use App\Domain\Incident\Incidencia;
use App\Domain\Incident\RepositorioIncidencia;
use Psr\Log\LoggerInterface;

/**
 * Publica `IncidenciaRegistrada` para n8n (RF-31) y, si el broker confirma, quita la notificación pendiente.
 * Si falla, la incidencia queda pendiente y la republica la tarea programada (RQ-INC-08).
 */
final class NotificacionIncidencia
{
    public const ROUTING_KEY = 'operaciones.incidencia.registrada';

    public const TIPO = 'IncidenciaRegistrada';

    public function __construct(
        private readonly PublicadorMensajes $publicador,
        private readonly RepositorioIncidencia $repositorio,
        private readonly LoggerInterface $log,
    ) {}

    public function notificar(Incidencia $incidencia, string $idCorrelacion): bool
    {
        try {
            $idMensaje = $this->publicador->publicarEvento(self::ROUTING_KEY, self::TIPO, self::datos($incidencia), $idCorrelacion);
        } catch (PublicacionFallida $e) {
            $this->log->error('No se pudo publicar IncidenciaRegistrada; la republicará la tarea programada', [
                'idCorrelacion' => $idCorrelacion,
                'idIncidencia' => $incidencia->id,
                'error' => $e->getMessage(),
            ]);

            return false;
        }

        $this->repositorio->marcarNotificada($incidencia->id);
        $this->log->info('IncidenciaRegistrada publicada', ['idCorrelacion' => $idCorrelacion, 'idMensaje' => $idMensaje, 'idIncidencia' => $incidencia->id]);

        return true;
    }

    /**
     * @return array<string, mixed> los `datos` del evento (spec-incidencias.md Historia 3)
     */
    public static function datos(Incidencia $incidencia): array
    {
        return [
            'idIncidencia' => $incidencia->id,
            'tipo' => $incidencia->tipo->value,
            'descripcion' => $incidencia->descripcion,
            'idParcela' => $incidencia->idParcela,
            'idCampania' => $incidencia->idCampania,
            'fechaObservacion' => $incidencia->fechaObservacion->format('Y-m-d\TH:i:s\Z'),
            'registradaPor' => ['id' => $incidencia->registradaPor->id, 'nombre' => $incidencia->registradaPor->nombre],
            'clasificacion' => $incidencia->clasificacion === null ? null : [
                'categoria' => $incidencia->clasificacion->categoria,
                'confianza' => $incidencia->clasificacion->confianza,
                'versionModelo' => $incidencia->clasificacion->versionModelo,
                'origen' => $incidencia->clasificacion->origen->value,
            ],
        ];
    }
}
