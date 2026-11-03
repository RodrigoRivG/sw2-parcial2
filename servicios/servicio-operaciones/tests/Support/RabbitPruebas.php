<?php

namespace Tests\Support;

use App\Infrastructure\Messaging\ConexionRabbitMq;
use App\Infrastructure\Messaging\TopologiaSaga;
use App\InterfaceAdapters\Messaging\ConsumidorRespuestasSaga;
use App\InterfaceAdapters\Messaging\FuenteMensajes;
use Illuminate\Support\Str;
use PhpAmqpLib\Channel\AMQPChannel;
use PhpAmqpLib\Connection\AbstractConnection;
use PhpAmqpLib\Message\AMQPMessage;

/**
 * Hace de inventario y de gestión en los tests de la Saga (spec-saga.md 2.9): lee los comandos de sus colas
 * y publica las respuestas, en el vhost `pruebas`.
 */
final class RabbitPruebas
{
    private static ?AbstractConnection $conexion = null;

    private static ?AMQPChannel $canal = null;

    public static function canal(): AMQPChannel
    {
        if (self::$canal === null || ! self::$canal->is_open()) {
            self::$conexion = ConexionRabbitMq::abrir();
            self::$canal = self::$conexion->channel();
            TopologiaSaga::declarar(self::$canal);
        }

        return self::$canal;
    }

    public static function purgarTodo(): void
    {
        foreach ([TopologiaSaga::COLA_INVENTARIO, TopologiaSaga::COLA_GESTION, TopologiaSaga::COLA_RESPUESTAS, TopologiaSaga::COLA_RESPUESTAS_DLQ] as $cola) {
            self::canal()->queue_purge($cola);
        }
    }

    /**
     * Lee y confirma el siguiente mensaje de la cola, esperando hasta $segundos.
     *
     * @return array<string, mixed>|null el sobre, con `_headers` si trae application_headers
     */
    public static function leer(string $cola, float $segundos = 3.0): ?array
    {
        $limite = microtime(true) + $segundos;
        do {
            $mensaje = self::canal()->basic_get($cola);
            if ($mensaje instanceof AMQPMessage) {
                $mensaje->ack();
                $sobre = json_decode($mensaje->getBody(), true) ?? ['_crudo' => $mensaje->getBody()];
                if ($mensaje->has('application_headers')) {
                    $sobre['_headers'] = $mensaje->get('application_headers')->getNativeData();
                }

                return $sobre;
            }
            usleep(50_000);
        } while (microtime(true) < $limite);

        return null;
    }

    /** @return list<array<string, mixed>> todos los mensajes que hay ahora en la cola */
    public static function leerTodos(string $cola): array
    {
        $mensajes = [];
        while (($sobre = self::leer($cola, 0.3)) !== null) {
            $mensajes[] = $sobre;
        }

        return $mensajes;
    }

    public static function contar(string $cola): int
    {
        [, $mensajes] = self::canal()->queue_declare($cola, true);

        return (int) $mensajes;
    }

    /**
     * Publica una respuesta de un participante en la cola del coordinador.
     *
     * @param  array<string, mixed>  $datos
     */
    public static function responder(string $tipo, string $idSaga, array $datos = [], ?string $idMensaje = null, string $origen = 'servicio-inventario'): void
    {
        self::publicarCrudo(json_encode([
            'idMensaje' => $idMensaje ?? (string) Str::uuid(),
            'idCorrelacion' => $idSaga,
            'tipo' => $tipo,
            'version' => 1,
            'fechaOcurrencia' => gmdate('Y-m-d\TH:i:s\Z'),
            'origen' => $origen,
            'datos' => ['idSaga' => $idSaga, ...$datos],
        ]));
    }

    public static function publicarCrudo(string $cuerpo): void
    {
        self::canal()->basic_publish(new AMQPMessage($cuerpo, ['content_type' => 'application/json']), '', TopologiaSaga::COLA_RESPUESTAS);
    }

    /** Corre el consumidor del servicio en el mismo proceso hasta procesar $maximo mensajes o quedarse 2 s sin mensajes. */
    public static function procesarRespuestas(int $maximo = 1): int
    {
        $consumidor = app(ConsumidorRespuestasSaga::class);

        return app(FuenteMensajes::class)->consumir(fn (string $cuerpo) => $consumidor->manejar($cuerpo), $maximo, 2.0);
    }
}
