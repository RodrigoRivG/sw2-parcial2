<?php

namespace App\InterfaceAdapters\Console;

use Illuminate\Console\Events\ScheduledTaskSkipped;
use Illuminate\Contracts\Cache\Repository as Cache;
use Psr\Log\LoggerInterface;

/**
 * Registra las tareas programadas que el scheduler omite (spec-saga.md RQ-SAG-14), para tener evidencia si una
 * tarea deja de correr. Distingue el solapamiento (su bloqueo existe) de otros filtros. Para no escribir un aviso
 * cada 10 s durante una incidencia larga, avisa como máximo una vez por tarea y motivo cada 5 minutos.
 */
final class AvisoTareaOmitida
{
    public const INTERVALO_SEGUNDOS = 300;

    public function __construct(
        private readonly Cache $cache,
        private readonly LoggerInterface $log,
    ) {}

    public function handle(ScheduledTaskSkipped $evento): void
    {
        $tarea = $evento->task;
        // ScheduledTaskSkipped también se emite por otros filtros y con el scheduler en pausa: solo se afirma
        // solapamiento cuando el bloqueo de la tarea existe.
        $motivo = $tarea->withoutOverlapping && $tarea->mutex->exists($tarea) ? 'SOLAPAMIENTO' : 'OTRA_CONDICION';
        $nombre = (string) ($tarea->command ?? $tarea->description ?? $tarea->mutexName());
        $clave = 'aviso-tarea-omitida:'.sha1($nombre.'|'.$motivo);
        if (! $this->cache->add($clave, true, self::INTERVALO_SEGUNDOS)) {
            return;
        }
        $this->log->warning('Tarea programada omitida', [
            'tarea' => $nombre,
            'motivo' => $motivo,
            'caducidadBloqueoMinutos' => $tarea->expiresAt,
            'avisoCadaSegundos' => self::INTERVALO_SEGUNDOS,
        ]);
    }
}
