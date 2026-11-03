<?php

use App\Application\Security\UsuarioAutenticado;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Tests\Support\Tokens;

beforeEach(function () {
    // Rutas solo de prueba, con los mismos middleware que las reales
    Route::prefix('api/operaciones/v1')->middleware(['jwt', 'rol:administrador'])->group(function () {
        Route::get('/prueba-seguridad', fn (Request $request) => [
            'id' => $request->attributes->get(UsuarioAutenticado::class)->id,
            'nombre' => $request->attributes->get(UsuarioAutenticado::class)->nombre,
        ]);
    });
});

function conToken(string $token): array
{
    return ['Authorization' => "Bearer {$token}"];
}

it('acepta un token válido y deja el usuario del token en la solicitud', function () {
    $this->getJson('/api/operaciones/v1/prueba-seguridad', conToken(Tokens::para(['administrador'], 'sub-123')))
        ->assertOk()
        ->assertExactJson(['id' => 'sub-123', 'nombre' => 'Usuario sub-123']);
});

it('usa preferred_username si el token no trae name', function () {
    $token = Tokens::para(['administrador'], 'sub-123', ['name' => null]);

    $this->getJson('/api/operaciones/v1/prueba-seguridad', conToken($token))
        ->assertOk()
        ->assertJson(['nombre' => 'sub-123']);
});

it('responde 401 sin token', function () {
    $this->getJson('/api/operaciones/v1/prueba-seguridad')
        ->assertStatus(401)
        ->assertJson(['codigo' => 'NO_AUTENTICADO']);
});

it('responde 401 con un token inválido', function (Closure $token) {
    $this->getJson('/api/operaciones/v1/prueba-seguridad', conToken($token()))
        ->assertStatus(401)
        ->assertJson(['codigo' => 'NO_AUTENTICADO']);
})->with([
    'firma de otra clave' => fn () => Tokens::para(['administrador'], clavePrivada: Tokens::otraClavePrivada()),
    'otro emisor' => fn () => Tokens::para(['administrador'], cambios: ['iss' => 'http://otro/realms/agro']),
    'otra audiencia' => fn () => Tokens::para(['administrador'], cambios: ['aud' => 'servicio-gestion']),
    'vencido' => fn () => Tokens::para(['administrador'], cambios: ['exp' => time() - 120]),
    'sin sub' => fn () => Tokens::para(['administrador'], cambios: ['sub' => null]),
    'texto cualquiera' => fn () => 'no-es-un-jwt',
]);

it('acepta la audiencia como texto', function () {
    $token = Tokens::para(['administrador'], cambios: ['aud' => 'servicio-operaciones']);

    $this->getJson('/api/operaciones/v1/prueba-seguridad', conToken($token))->assertOk();
});

it('responde 403 si el usuario no tiene el rol', function () {
    $this->getJson('/api/operaciones/v1/prueba-seguridad', conToken(Tokens::para(['gerencia', 'tecnico_campo'])))
        ->assertStatus(403)
        ->assertJson(['codigo' => 'SIN_PERMISO']);
});

it('devuelve el X-Correlation-Id recibido también en 401 y 403', function () {
    $this->getJson('/api/operaciones/v1/prueba-seguridad', ['X-Correlation-Id' => 'abc-123'])
        ->assertStatus(401)
        ->assertHeader('X-Correlation-Id', 'abc-123')
        ->assertJson(['idCorrelacion' => 'abc-123']);

    $this->getJson('/api/operaciones/v1/prueba-seguridad', [...conToken(Tokens::para(['gerencia'])), 'X-Correlation-Id' => 'def-456'])
        ->assertStatus(403)
        ->assertHeader('X-Correlation-Id', 'def-456');
});

it('genera un X-Correlation-Id si no llega o no es válido', function () {
    $respuesta = $this->getJson('/salud/liveness', ['X-Correlation-Id' => 'con espacios y ñ']);

    expect($respuesta->headers->get('X-Correlation-Id'))->toMatch('/^[0-9a-f-]{36}$/');
});
