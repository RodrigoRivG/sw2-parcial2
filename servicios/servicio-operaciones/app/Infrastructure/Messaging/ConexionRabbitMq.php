<?php

namespace App\Infrastructure\Messaging;

use PhpAmqpLib\Channel\AMQPChannel;
use PhpAmqpLib\Connection\AbstractConnection;
use PhpAmqpLib\Connection\AMQPConnectionConfig;
use PhpAmqpLib\Connection\AMQPConnectionFactory;
use Throwable;

/**
 * Una conexión por proceso, abierta al primer uso; AMQPS si RABBITMQ_SSL es true (constitución §9).
 * Al abrirla declara la topología de la Saga, para no perder comandos si los participantes no arrancaron.
 * Publicación y consumo usan canales separados: el de publicación está en modo confirmación.
 */
final class ConexionRabbitMq
{
    private ?AbstractConnection $conexion = null;

    private ?AMQPChannel $publicacion = null;

    private ?bool $ultimaConfirmacion = null;

    public function canalPublicacion(): AMQPChannel
    {
        if ($this->publicacion === null || ! $this->publicacion->is_open()) {
            $canal = $this->conexion()->channel();
            $canal->set_ack_handler(function () {
                $this->ultimaConfirmacion = true;
            });
            $canal->set_nack_handler(function () {
                $this->ultimaConfirmacion = false;
            });
            $canal->confirm_select();
            $this->publicacion = $canal;
        }
        $this->ultimaConfirmacion = null;

        return $this->publicacion;
    }

    /** true si el broker confirmó la última publicación, false si la rechazó, null si no respondió. */
    public function ultimaConfirmacion(): ?bool
    {
        return $this->ultimaConfirmacion;
    }

    public function canalNuevo(): AMQPChannel
    {
        return $this->conexion()->channel();
    }

    public function conexion(): AbstractConnection
    {
        if ($this->conexion === null || ! $this->conexion->isConnected()) {
            $this->conexion = self::abrir();
            $canal = $this->conexion->channel();
            TopologiaSaga::declarar($canal);
            $canal->close();
        }

        return $this->conexion;
    }

    /** Descarta la conexión tras un error, para abrir una nueva en el próximo uso. */
    public function reiniciar(): void
    {
        try {
            $this->conexion?->close();
        } catch (Throwable) {
            // La conexión ya estaba rota
        }
        $this->conexion = null;
        $this->publicacion = null;
    }

    public static function abrir(float $tiempoLimite = 3.0): AbstractConnection
    {
        $config = new AMQPConnectionConfig;
        $config->setHost((string) config('rabbitmq.host'));
        $config->setPort((int) config('rabbitmq.port'));
        $config->setUser((string) config('rabbitmq.usuario'));
        $config->setPassword((string) config('rabbitmq.clave'));
        $config->setVhost((string) config('rabbitmq.vhost'));
        $config->setConnectionTimeout($tiempoLimite);
        $config->setReadTimeout(10);
        $config->setWriteTimeout(10);
        $config->setHeartbeat(30);
        if (config('rabbitmq.ssl')) {
            $config->setIsSecure(true);
        }

        return AMQPConnectionFactory::create($config);
    }
}
