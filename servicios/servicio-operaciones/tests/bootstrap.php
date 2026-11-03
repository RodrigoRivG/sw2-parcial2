<?php

/*
 * Arranque de los tests (README D-17): crea las tablas de DynamoDB con un prefijo propio de esta corrida
 * y las borra al terminar, para no pisar los datos de desarrollo ni otras corridas.
 */

use App\Infrastructure\Persistence\DynamoDb\CreadorTablas;
use App\Infrastructure\Persistence\DynamoDb\NombresTablas;
use Aws\DynamoDb\DynamoDbClient;
use Aws\S3\S3Client;
use GuzzleHttp\Client;

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

// Bucket de los tests en LocalStack (idempotente)
$s3 = new S3Client([
    'region' => getenv('AWS_DEFAULT_REGION') ?: 'us-east-1',
    'version' => '2006-03-01',
    'endpoint' => getenv('AWS_ENDPOINT'),
    'use_path_style_endpoint' => true,
    'credentials' => ['key' => getenv('AWS_ACCESS_KEY_ID'), 'secret' => getenv('AWS_SECRET_ACCESS_KEY')],
]);
if (! $s3->doesBucketExistV2((string) getenv('AWS_BUCKET'))) {
    $s3->createBucket(['Bucket' => getenv('AWS_BUCKET')]);
}

// vhost de RabbitMQ de los tests, por la API de administración (idempotente)
$gestionRabbit = new Client([
    'base_uri' => rtrim((string) getenv('RABBITMQ_GESTION_URL'), '/').'/',
    'auth' => [getenv('RABBITMQ_USER'), getenv('RABBITMQ_PASSWORD')],
    'timeout' => 10,
]);
$vhost = rawurlencode((string) getenv('RABBITMQ_VHOST'));
$gestionRabbit->put("api/vhosts/{$vhost}");
$gestionRabbit->put("api/permissions/{$vhost}/".rawurlencode((string) getenv('RABBITMQ_USER')), [
    'json' => ['configure' => '.*', 'write' => '.*', 'read' => '.*'],
]);

// Los procesos hijos de EnParalelo heredan esta función: solo el proceso original borra las tablas
$pidOriginal = getmypid();
register_shutdown_function(function () use ($creador, $pidOriginal): void {
    if (getmypid() === $pidOriginal) {
        $creador->eliminarTodas();
    }
});
