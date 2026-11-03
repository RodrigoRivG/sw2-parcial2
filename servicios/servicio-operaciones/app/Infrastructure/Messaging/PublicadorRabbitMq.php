<?php

namespace App\Infrastructure\Messaging;

use App\Application\Contracts\PublicacionFallida;
use App\Application\Contracts\PublicadorMensajes;
use App\Application\Contracts\Reloj;
use App\Domain\Saga\Participante;
use App\Domain\Shared\Uuid;
use PhpAmqpLib\Message\AMQPMessage;
use Throwable;

/**
 * Publica con el sobre común, persistente y con confirmación del broker (spec-saga.md 2.3).
 */
final class PublicadorRabbitMq implements PublicadorMensajes
{
    public const ORIGEN = 'servicio-operaciones';

    private const SEGUNDOS_CONFIRMACION = 5;

    public function __construct(
        private readonly ConexionRabbitMq $conexion,
        private readonly Reloj $reloj,
    ) {}

    public function enviarComando(Participante $destino, string $tipo, array $datos, string $idCorrelacion): string
    {
        $idMensaje = Uuid::v4();
        $this->publicar('', TopologiaSaga::colaDe($destino), [
            'idMensaje' => $idMensaje,
            'idCorrelacion' => $idCorrelacion,
            'tipo' => $tipo,
            'version' => 1,
            'fechaOcurrencia' => $this->reloj->ahora()->format('Y-m-d\TH:i:s\Z'),
            'origen' => self::ORIGEN,
            'datos' => $datos,
        ], $idMensaje, $idCorrelacion);

        return $idMensaje;
    }

    public function publicarEvento(string $routingKey, string $tipo, array $datos, string $idCorrelacion): string
    {
        $idMensaje = Uuid::v4();
        $this->publicar(TopologiaSaga::EXCHANGE_EVENTOS, $routingKey, [
            'idMensaje' => $idMensaje,
            'idCorrelacion' => $idCorrelacion,
            'tipo' => $tipo,
            'version' => 1,
            'fechaOcurrencia' => $this->reloj->ahora()->format('Y-m-d\TH:i:s\Z'),
            'origen' => self::ORIGEN,
            'datos' => $datos,
        ], $idMensaje, $idCorrelacion);

        return $idMensaje;
    }

    /**
     * @param  array<string, mixed>  $sobre
     */
    private function publicar(string $exchange, string $routingKey, array $sobre, string $idMensaje, string $idCorrelacion): void
    {
        // Un reintento con una conexión nueva: la anterior pudo cerrarse por inactividad
        for ($intento = 1; $intento <= 2; $intento++) {
            try {
                $this->publicarUnaVez($exchange, $routingKey, $sobre, $idMensaje, $idCorrelacion);

                return;
            } catch (Throwable $e) {
                $this->conexion->reiniciar();
                if ($intento === 2) {
                    throw new PublicacionFallida("No se pudo publicar en {$routingKey}: {$e->getMessage()}", previous: $e);
                }
            }
        }
    }

    /**
     * @param  array<string, mixed>  $sobre
     */
    private function publicarUnaVez(string $exchange, string $routingKey, array $sobre, string $idMensaje, string $idCorrelacion): void
    {
        $canal = $this->conexion->canalPublicacion();

        $canal->basic_publish(new AMQPMessage(json_encode($sobre, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR), [
            'content_type' => 'application/json',
            'delivery_mode' => AMQPMessage::DELIVERY_MODE_PERSISTENT,
            'message_id' => $idMensaje,
            'correlation_id' => $idCorrelacion,
        ]), $exchange, $routingKey);
        $canal->wait_for_pending_acks(self::SEGUNDOS_CONFIRMACION);

        if ($this->conexion->ultimaConfirmacion() !== true) {
            throw new PublicacionFallida("El broker no confirmó el mensaje {$idMensaje}.");
        }
    }
}
