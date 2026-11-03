<?php

// Los demás servicios se consultan solo a través del API Gateway (constitución §7).
return [
    'api_gateway_url' => env('API_GATEWAY_URL'),
    'tiempo_limite_gestion_segundos' => (float) env('GESTION_TIEMPO_LIMITE_SEGUNDOS', 2),
];
