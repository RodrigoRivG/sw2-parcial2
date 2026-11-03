<?php

namespace App\Infrastructure\Messaging;

use App\InterfaceAdapters\Messaging\FuenteMensajes;
use PhpAmqpLib\Exception\AMQPTimeoutException;
use PhpAmqpLib\Message\AMQPMessage;
use PhpAmqpLib\Wire\AMQPTable;

/**
 * Consume `servicio-operaciones.respuestas-saga` con prefetch 1 y confirmación manual (spec-saga.md 2.4).
 * La DLQ se alimenta publicando el mensaje en `servicio-operaciones.respuestas-saga.dlq` antes de confirmarlo,
 * porque la cola de respuestas no tiene argumentos de dead-letter (README D-13).
 */
final class FuenteMensajesRabbitMq implements FuenteMensajes
{
    public function __construct(private readonly ConexionRabbitMq $conexion) {}

    public function consumir(callable $manejador, ?int $maximo = null, ?float $segundosSinMensajes = null): int
    {
        $canal = $this->conexion->canalNuevo();
        $canal->basic_qos(0, 1, false);
        $procesados = 0;
        $ultimoMensaje = microtime(true);

        $etiqueta = $canal->basic_consume(TopologiaSaga::COLA_RESPUESTAS, '', false, false, false, false,
            function (AMQPMessage $mensaje) use ($manejador, &$procesados, &$ultimoMensaje) {
                $motivo = $manejador($mensaje->getBody());
                if ($motivo !== null) {
                    // Si la DLQ no confirma, se lanza la excepción y el mensaje no se confirma: vuelve a la cola
                    $this->enviarADlq($mensaje, $motivo);
                }
                $mensaje->ack();
                $procesados++;
                $ultimoMensaje = microtime(true);
            });

        while ($canal->is_consuming()) {
            if ($maximo !== null && $procesados >= $maximo) {
                break;
            }
            if ($segundosSinMensajes !== null && microtime(true) - $ultimoMensaje >= $segundosSinMensajes) {
                break;
            }
            try {
                $canal->wait(null, false, 1);
            } catch (AMQPTimeoutException) {
                // Sin mensajes en el último segundo: se mantiene viva la conexión
                $this->conexion->conexion()->checkHeartBeat();
            }
        }

        $canal->basic_cancel($etiqueta);
        $canal->close();

        return $procesados;
    }

    private function enviarADlq(AMQPMessage $mensaje, string $motivo): void
    {
        $canal = $this->conexion->canalPublicacion();
        $canal->basic_publish(new AMQPMessage($mensaje->getBody(), [
            'content_type' => 'application/json',
            'delivery_mode' => AMQPMessage::DELIVERY_MODE_PERSISTENT,
            'application_headers' => new AMQPTable([
                'x-motivo' => mb_substr($motivo, 0, 500),
                'x-cola-origen' => TopologiaSaga::COLA_RESPUESTAS,
            ]),
        ]), '', TopologiaSaga::COLA_RESPUESTAS_DLQ);
        $canal->wait_for_pending_acks(5);
        if ($this->conexion->ultimaConfirmacion() !== true) {
            throw new \RuntimeException('La DLQ no confirmó el mensaje; se deja sin confirmar para no perderlo.');
        }
    }
}
