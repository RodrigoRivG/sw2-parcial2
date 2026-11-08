<?php

use App\InterfaceAdapters\Console\AvisoTareaOmitida;
use Illuminate\Cache\ArrayStore;
use Illuminate\Cache\Repository;
use Illuminate\Console\Events\ScheduledTaskSkipped;
use Illuminate\Console\Scheduling\Event;
use Illuminate\Console\Scheduling\EventMutex;
use Psr\Log\AbstractLogger;

it('avisa una sola vez por tarea y motivo, y distingue el solapamiento de otras condiciones', function () {
    $mutex = new class implements EventMutex
    {
        public bool $existe = true;

        public function create(Event $event)
        {
            return true;
        }

        public function exists(Event $event)
        {
            return $this->existe;
        }

        public function forget(Event $event) {}
    };
    $log = new class extends AbstractLogger
    {
        /** @var list<array<string, mixed>> */
        public array $avisos = [];

        public function log($level, $message, array $context = []): void
        {
            $this->avisos[] = ['nivel' => $level, 'mensaje' => (string) $message] + $context;
        }
    };
    $tarea = (new Event($mutex, 'php artisan sagas:reanudar'))->withoutOverlapping(2);
    $aviso = new AvisoTareaOmitida(new Repository(new ArrayStore), $log);

    $aviso->handle(new ScheduledTaskSkipped($tarea));
    $aviso->handle(new ScheduledTaskSkipped($tarea));
    $mutex->existe = false;
    $aviso->handle(new ScheduledTaskSkipped($tarea));

    expect($log->avisos)->toHaveCount(2)
        ->and($log->avisos[0])->toMatchArray(['nivel' => 'warning', 'tarea' => 'php artisan sagas:reanudar', 'motivo' => 'SOLAPAMIENTO', 'caducidadBloqueoMinutos' => 2])
        ->and($log->avisos[1]['motivo'])->toBe('OTRA_CONDICION');
});
