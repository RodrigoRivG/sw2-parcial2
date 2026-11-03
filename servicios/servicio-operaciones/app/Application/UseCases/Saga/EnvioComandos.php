<?php

namespace App\Application\UseCases\Saga;

use App\Application\Contracts\PublicacionFallida;
use App\Application\Contracts\PublicadorMensajes;
use App\Domain\Saga\PasoSaga;
use App\Domain\Saga\Saga;
use Psr\Log\LoggerInterface;

/**
 * Publica el comando de un paso después de guardar la Saga. Si el broker falla, solo se registra:
 * la Saga ya está guardada con su fecha límite y la tarea de recuperación lo reenvía (Historia 6, escenario 4).
 */
final class EnvioComandos
{
    public function __construct(
        private readonly PublicadorMensajes $publicador,
        private readonly LoggerInterface $log,
    ) {}

    public function enviar(Saga $saga, PasoSaga $paso): void
    {
        $comando = ComandoSaga::para($saga, $paso);
        try {
            $idMensaje = $this->publicador->enviarComando($comando->destino, $comando->tipo, $comando->datos, $saga->idSaga);
            $this->log->info('Comando de la Saga enviado', [
                'idCorrelacion' => $saga->idSaga,
                'idMensaje' => $idMensaje,
                'tipo' => $comando->tipo,
                'intento' => $saga->paso($paso)->intentos,
            ]);
        } catch (PublicacionFallida $e) {
            $this->log->error('No se pudo publicar el comando de la Saga; lo reenviará la recuperación', [
                'idCorrelacion' => $saga->idSaga,
                'tipo' => $comando->tipo,
                'error' => $e->getMessage(),
            ]);
        }
    }
}
