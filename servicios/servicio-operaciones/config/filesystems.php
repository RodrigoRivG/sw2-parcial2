<?php

// Solo el disco local interno; las fotos van a S3 con el SDK (spec-incidencias.md). Sin rutas públicas de archivos.
return [
    'default' => 'local',
    'disks' => [
        'local' => [
            'driver' => 'local',
            'root' => storage_path('app/private'),
            'serve' => false,
            'throw' => false,
        ],
    ],
];
