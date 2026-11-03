<?php

// RabbitMQ: AMQP en local y en los tests, AMQPS en la nube (constitución §9 y §10).
return [
    'host' => env('RABBITMQ_HOST', 'rabbitmq'),
    'port' => (int) env('RABBITMQ_PORT', 5672),
    'usuario' => env('RABBITMQ_USER'),
    'clave' => env('RABBITMQ_PASSWORD'),
    'vhost' => env('RABBITMQ_VHOST', '/'),
    'ssl' => filter_var(env('RABBITMQ_SSL', false), FILTER_VALIDATE_BOOL),
    // Espera entre reintentos de una respuesta que falla por un error técnico (README D-14): 1 s, 2 s y 4 s
    'esperas_reintento_ms' => array_map('intval', explode(',', (string) env('RABBITMQ_ESPERAS_REINTENTO_MS', '1000,2000,4000'))),
];
