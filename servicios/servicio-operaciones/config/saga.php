<?php

// Tiempos de la Saga (spec-saga.md RQ-SAG-06).
return [
    'tiempo_limite_segundos' => (int) env('SAGA_TIEMPO_LIMITE_SEGUNDOS', 30),
    'maximo_envios' => (int) env('SAGA_MAXIMO_ENVIOS', 4),
    'espera_maxima_compensacion_segundos' => (int) env('SAGA_ESPERA_MAXIMA_COMPENSACION_SEGUNDOS', 600),
];
