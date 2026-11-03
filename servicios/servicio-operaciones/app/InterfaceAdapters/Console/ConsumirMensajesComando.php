<?php

namespace App\InterfaceAdapters\Console;

use App\InterfaceAdapters\Messaging\ConsumidorRespuestasSaga;
use App\InterfaceAdapters\Messaging\FuenteMensajes;
use Illuminate\Console\Command;
use Throwable;

/**
 * Proceso de larga duración: `servicio-operaciones-consumidor` en Docker Compose (spec-saga.md 2.4).
 * Si la conexión se pierde, termina con error y Docker lo reinicia; lo no confirmado vuelve a la cola.
 */
final class ConsumirMensajesComando extends Command
{
    protected $signature = 'operaciones:consumir-respuestas
        {--maximo= : Termina después de procesar esta cantidad de mensajes}
        {--segundos= : Termina si no llega ningún mensaje en este tiempo}';

    protected $description = 'Consume las respuestas de los participantes de la Saga.';

    public function handle(FuenteMensajes $fuente, ConsumidorRespuestasSaga $consumidor): int
    {
        try {
            $procesados = $fuente->consumir(
                fn (string $cuerpo) => $consumidor->manejar($cuerpo),
                $this->option('maximo') === null ? null : (int) $this->option('maximo'),
                $this->option('segundos') === null ? null : (float) $this->option('segundos'),
            );
        } catch (Throwable $e) {
            $this->error("El consumidor se detuvo: {$e->getMessage()}");
            report($e);

            return self::FAILURE;
        }
        $this->info("Mensajes procesados: {$procesados}");

        return self::SUCCESS;
    }
}
