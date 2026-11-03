<?php

use Monolog\Formatter\JsonFormatter;
use Monolog\Handler\NullHandler;
use Monolog\Handler\StreamHandler;

// Logs estructurados en JSON a stderr; el Context de Laravel agrega idCorrelacion (constitución §11).
return [
    'default' => env('LOG_CHANNEL', 'stderr'),

    'deprecations' => [
        'channel' => env('LOG_DEPRECATIONS_CHANNEL', 'null'),
        'trace' => false,
    ],

    'channels' => [
        'stderr' => [
            'driver' => 'monolog',
            'level' => env('LOG_LEVEL', 'info'),
            'handler' => StreamHandler::class,
            'handler_with' => ['stream' => 'php://stderr'],
            'formatter' => JsonFormatter::class,
        ],
        'null' => [
            'driver' => 'monolog',
            'handler' => NullHandler::class,
        ],
    ],
];
