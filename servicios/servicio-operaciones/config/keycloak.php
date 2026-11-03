<?php

// Validación del JWT y token de la cuenta de servicio (constitución §9, README D-12).
return [
    'emisor' => env('KEYCLOAK_ISSUER'),
    'jwks_uri' => env('KEYCLOAK_JWKS_URI'),
    'audiencia' => env('KEYCLOAK_AUDIENCE'),
    'token_url' => env('KEYCLOAK_TOKEN_URL'),
    'client_id' => env('KEYCLOAK_CLIENT_ID'),
    'client_secret' => env('KEYCLOAK_CLIENT_SECRET'),
];
