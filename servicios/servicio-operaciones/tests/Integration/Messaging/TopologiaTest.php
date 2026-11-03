<?php

use App\Infrastructure\Messaging\ConexionRabbitMq;
use App\Infrastructure\Messaging\TopologiaSaga;
use GuzzleHttp\Client;
use PhpAmqpLib\Wire\AMQPTable;

/** @return array<string, mixed> la cola según la API de administración de RabbitMQ */
function colaEnRabbit(string $cola): array
{
    $cliente = new Client([
        'base_uri' => rtrim((string) env('RABBITMQ_GESTION_URL'), '/').'/',
        'auth' => [env('RABBITMQ_USER'), env('RABBITMQ_PASSWORD')],
    ]);

    $datos = json_decode((string) $cliente->get('api/queues/'.rawurlencode((string) env('RABBITMQ_VHOST')).'/'.rawurlencode($cola))->getBody(), true);
    // RabbitMQ 4 informa el tipo por defecto (classic) aunque nadie lo declare
    unset($datos['arguments']['x-queue-type']);

    return $datos;
}

it('declara las cuatro colas de la Saga con los argumentos acordados con los participantes (README D-13)', function () {
    app(ConexionRabbitMq::class)->conexion();

    foreach ([TopologiaSaga::COLA_INVENTARIO, TopologiaSaga::COLA_GESTION] as $cola) {
        expect(colaEnRabbit($cola))->toMatchArray([
            'durable' => true,
            'arguments' => ['x-dead-letter-exchange' => '', 'x-dead-letter-routing-key' => "{$cola}.dlq"],
        ]);
    }
    foreach ([TopologiaSaga::COLA_RESPUESTAS, TopologiaSaga::COLA_RESPUESTAS_DLQ] as $cola) {
        expect(colaEnRabbit($cola))->toMatchArray(['durable' => true, 'arguments' => []]);
    }
});

it('declarar después de inventario y gestión no falla: los argumentos coinciden', function () {
    // Así las declaran inventario (topologia-saga.ts) y gestión (ConfiguracionRabbit)
    $canal = ConexionRabbitMq::abrir()->channel();
    $canal->queue_declare(TopologiaSaga::COLA_INVENTARIO, false, true, false, false, false,
        new AMQPTable(['x-dead-letter-exchange' => '', 'x-dead-letter-routing-key' => 'servicio-inventario.comandos.dlq']));
    $canal->queue_declare(TopologiaSaga::COLA_RESPUESTAS, false, true, false, false);

    TopologiaSaga::declarar($canal);

    expect($canal->is_open())->toBeTrue();
});
