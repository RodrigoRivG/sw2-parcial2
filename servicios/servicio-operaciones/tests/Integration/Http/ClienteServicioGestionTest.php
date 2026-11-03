<?php

use App\Application\Contracts\CampaniaNoDisponible;
use App\Infrastructure\Http\ClienteServicioGestion;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Context;
use Illuminate\Support\Facades\Http;

const URL_ESTADO = 'http://gateway.pruebas/api/gestion/v1/campanias/c1/estado';
const URL_TOKEN = 'http://keycloak.pruebas/realms/agro/protocol/openid-connect/token';

function gestionResponde(mixed $respuesta): void
{
    Http::fake([
        URL_TOKEN => Http::response(['access_token' => 'token-1', 'expires_in' => 300]),
        URL_ESTADO => $respuesta,
    ]);
}

it('devuelve la campaña con el token de servicio y el X-Correlation-Id', function () {
    Context::add('idCorrelacion', 'corr-9');
    gestionResponde(Http::response(['id' => 'C1', 'idParcela' => 'P1', 'idCultivo' => 'x', 'estado' => 'EN_CURSO', 'fechaInicio' => '2026-11-01', 'fechaFin' => '2027-01-01']));

    $campania = app(ClienteServicioGestion::class)->consultar('c1');

    expect($campania->id)->toBe('c1')->and($campania->idParcela)->toBe('p1')->and($campania->estado)->toBe('EN_CURSO');
    Http::assertSent(fn (Request $r) => $r->url() === URL_ESTADO
        && $r->hasHeader('Authorization', 'Bearer token-1')
        && $r->hasHeader('X-Correlation-Id', 'corr-9'));
    Http::assertSent(fn (Request $r) => $r->url() === URL_TOKEN
        && $r['grant_type'] === 'client_credentials'
        && $r['client_id'] === 'servicio-operaciones'
        && $r['client_secret'] === 'secreto-pruebas');
});

it('pide el token una sola vez mientras está vigente', function () {
    gestionResponde(Http::response(['id' => 'c1', 'idParcela' => 'p1', 'estado' => 'EN_CURSO']));
    $cliente = app(ClienteServicioGestion::class);

    $cliente->consultar('c1');
    $cliente->consultar('c1');

    Http::assertSentCount(3);
});

it('devuelve null solo si gestión responde CAMPANIA_NO_ENCONTRADA', function () {
    gestionResponde(Http::response(['codigo' => 'CAMPANIA_NO_ENCONTRADA'], 404));

    expect(app(ClienteServicioGestion::class)->consultar('c1'))->toBeNull();
});

it('trata como no disponible cualquier otro fallo', function (mixed $respuesta) {
    gestionResponde($respuesta);

    expect(fn () => app(ClienteServicioGestion::class)->consultar('c1'))->toThrow(CampaniaNoDisponible::class);
})->with([
    '404 del Gateway' => fn () => Http::response('Not Found', 404),
    '500' => fn () => Http::response(['codigo' => 'ERROR_INTERNO'], 500),
    '503' => fn () => Http::response('', 503),
    '401' => fn () => Http::response(['codigo' => 'NO_AUTENTICADO'], 401),
    '403' => fn () => Http::response(['codigo' => 'SIN_PERMISO'], 403),
    'respuesta sin formato' => fn () => Http::response(['estado' => 'EN_CURSO']),
    'tiempo límite' => fn () => fn () => throw new ConnectionException('cURL error 28: Operation timed out after 2001 milliseconds'),
]);

it('olvida el token si gestión lo rechaza, para pedir uno nuevo la próxima vez', function () {
    Http::fake([
        URL_TOKEN => Http::sequence()->push(['access_token' => 'viejo', 'expires_in' => 300])->push(['access_token' => 'nuevo', 'expires_in' => 300]),
        URL_ESTADO => Http::sequence()->push(['codigo' => 'NO_AUTENTICADO'], 401)->push(['id' => 'c1', 'idParcela' => 'p1', 'estado' => 'EN_CURSO']),
    ]);
    $cliente = app(ClienteServicioGestion::class);

    expect(fn () => $cliente->consultar('c1'))->toThrow(CampaniaNoDisponible::class);
    $cliente->consultar('c1');

    Http::assertSent(fn (Request $r) => $r->url() === URL_ESTADO && $r->hasHeader('Authorization', 'Bearer nuevo'));
});

it('si Keycloak no entrega el token, gestión cuenta como no disponible', function (mixed $token) {
    Http::fake([URL_TOKEN => $token]);

    expect(fn () => app(ClienteServicioGestion::class)->consultar('c1'))->toThrow(CampaniaNoDisponible::class);
})->with([
    'rechazo' => fn () => Http::response(['error' => 'unauthorized_client'], 401),
    'sin respuesta' => fn () => fn () => throw new ConnectionException('timeout'),
]);
