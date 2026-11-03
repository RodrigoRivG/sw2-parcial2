<?php

/*
 * Arranque de los tests (README D-17): crea las tablas de DynamoDB con un prefijo propio de esta corrida
 * y las borra al terminar, para no pisar los datos de desarrollo ni otras corridas.
 */

use App\Infrastructure\Persistence\DynamoDb\CreadorTablas;
use App\Infrastructure\Persistence\DynamoDb\NombresTablas;
use Aws\DynamoDb\DynamoDbClient;

require __DIR__.'/../vendor/autoload.php';

$prefijo = 'pruebas_'.bin2hex(random_bytes(4)).'_';
foreach (['putenv', 'env', 'server'] as $destino) {
    match ($destino) {
        'putenv' => putenv("DYNAMODB_PREFIJO_TABLAS={$prefijo}"),
        'env' => $_ENV['DYNAMODB_PREFIJO_TABLAS'] = $prefijo,
        'server' => $_SERVER['DYNAMODB_PREFIJO_TABLAS'] = $prefijo,
    };
}

$creador = new CreadorTablas(
    new DynamoDbClient([
        'region' => getenv('AWS_DEFAULT_REGION') ?: 'us-east-1',
        'version' => '2012-08-10',
        'endpoint' => getenv('DYNAMODB_ENDPOINT'),
        'credentials' => ['key' => getenv('AWS_ACCESS_KEY_ID'), 'secret' => getenv('AWS_SECRET_ACCESS_KEY')],
    ]),
    new NombresTablas($prefijo),
    __DIR__.'/../database/dynamodb/tablas.json',
);
$creador->crearFaltantes();

// Los procesos hijos de EnParalelo heredan esta función: solo el proceso original borra las tablas
$pidOriginal = getmypid();
register_shutdown_function(function () use ($creador, $pidOriginal): void {
    if (getmypid() === $pidOriginal) {
        $creador->eliminarTodas();
    }
});
