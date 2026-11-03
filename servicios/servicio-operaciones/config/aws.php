<?php

// AWS: DynamoDB y S3 (constitución §2). En local apuntan a DynamoDB Local y LocalStack (README D-16).
return [
    'region' => env('AWS_DEFAULT_REGION', 'us-east-1'),
    'clave' => env('AWS_ACCESS_KEY_ID'),
    'secreto' => env('AWS_SECRET_ACCESS_KEY'),
    'dynamodb' => [
        'endpoint' => env('DYNAMODB_ENDPOINT'),
        'prefijo_tablas' => env('DYNAMODB_PREFIJO_TABLAS', ''),
    ],
    's3' => [
        'endpoint' => env('AWS_ENDPOINT'),
        'endpoint_publico' => env('AWS_ENDPOINT_PUBLICO'),
        'path_style' => filter_var(env('AWS_USE_PATH_STYLE_ENDPOINT', false), FILTER_VALIDATE_BOOL),
        'bucket' => env('AWS_BUCKET'),
    ],
];
