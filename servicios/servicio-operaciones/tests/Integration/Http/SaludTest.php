<?php

use Aws\DynamoDb\DynamoDbClient;

it('responde liveness sin token', function () {
    $this->getJson('/salud/liveness')
        ->assertOk()
        ->assertExactJson(['estado' => 'UP']);
});

it('responde readiness y /salud con DynamoDB disponible', function (string $ruta) {
    $this->getJson($ruta)
        ->assertOk()
        ->assertJson(['estado' => 'UP', 'componentes' => ['dynamodb' => ['estado' => 'UP']]]);
})->with(['/salud/readiness', '/salud']);

it('responde 503 en readiness si DynamoDB no responde', function () {
    $this->app->singleton(DynamoDbClient::class, fn () => new DynamoDbClient([
        'region' => 'us-east-1',
        'version' => '2012-08-10',
        'endpoint' => 'http://127.0.0.1:1',
        'credentials' => ['key' => 'test', 'secret' => 'test'],
        'retries' => 0,
        'http' => ['connect_timeout' => 1, 'timeout' => 1],
    ]));

    $this->getJson('/salud/readiness')
        ->assertStatus(503)
        ->assertJson(['estado' => 'DOWN', 'componentes' => ['dynamodb' => ['estado' => 'DOWN']]]);
});

it('sirve el contrato OpenAPI sin token', function () {
    $this->get('/api-docs')
        ->assertOk()
        ->assertHeader('Content-Type', 'application/yaml; charset=utf-8');
});
