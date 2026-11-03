<?php

namespace App\Application\Contracts;

use App\Domain\Saga\Participante;

/**
 * Publica en RabbitMQ con el sobre común y espera la confirmación del broker (constitución §10).
 */
interface PublicadorMensajes
{
    /**
     * Comando de la Saga a la cola del participante (spec-saga.md RQ-SAG-02).
     *
     * @param  array<string, mixed>  $datos
     * @return string idMensaje
     *
     * @throws PublicacionFallida
     */
    public function enviarComando(Participante $destino, string $tipo, array $datos, string $idCorrelacion): string;
}
