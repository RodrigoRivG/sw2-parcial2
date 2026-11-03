<?php

use App\Domain\Shared\ExcepcionDominio;
use App\InterfaceAdapters\Http\Middleware\ExigirJsonValido;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Tests\Support\Tokens;

beforeEach(function () {
    Route::prefix('api/operaciones/v1')->middleware(['jwt', ExigirJsonValido::class])->group(function () {
        Route::post('/prueba-errores', function (Request $request) {
            $request->validate(['idOperacion' => ['required', 'uuid']]);

            return ['ok' => true];
        });
        Route::get('/prueba-errores/interno', fn () => throw new RuntimeException('detalle secreto'));
        Route::get('/prueba-errores/regla', fn () => throw ExcepcionDominio::reglaNegocio('CAMPANIA_FINALIZADA', 'La campaña está finalizada.', [['campo' => 'idCampania']]));
        Route::get('/prueba-errores/conflicto', fn () => throw ExcepcionDominio::conflicto('CONFLICTO_IDEMPOTENCIA', 'Otro contenido.'));
        Route::get('/prueba-errores/no-encontrado', fn () => throw ExcepcionDominio::noEncontrado('LABOR_NO_ENCONTRADA', 'No existe.'));
    });
});

function tokenErrores(): array
{
    return ['Authorization' => 'Bearer '.Tokens::para(['administrador'])];
}

it('responde 400 DATOS_INVALIDOS con un detalle por campo', function () {
    $this->postJson('/api/operaciones/v1/prueba-errores', ['idOperacion' => 'no-uuid'], tokenErrores())
        ->assertStatus(400)
        ->assertJsonStructure(['codigo', 'mensaje', 'detalles' => [['campo', 'mensaje']], 'idCorrelacion'])
        ->assertJson(['codigo' => 'DATOS_INVALIDOS', 'detalles' => [['campo' => 'idOperacion']]]);
});

it('responde 400 con un JSON mal formado', function () {
    $this->call('POST', '/api/operaciones/v1/prueba-errores', [], [], [], [
        'CONTENT_TYPE' => 'application/json',
        'HTTP_ACCEPT' => 'application/json',
        'HTTP_AUTHORIZATION' => tokenErrores()['Authorization'],
    ], '{"idOperacion": ')
        ->assertStatus(400)
        ->assertJson(['codigo' => 'DATOS_INVALIDOS']);
});

it('traduce los errores del dominio a 404, 409 y 422', function (string $ruta, int $estado, string $codigo) {
    $this->getJson("/api/operaciones/v1/prueba-errores/{$ruta}", tokenErrores())
        ->assertStatus($estado)
        ->assertJson(['codigo' => $codigo]);
})->with([
    ['no-encontrado', 404, 'LABOR_NO_ENCONTRADA'],
    ['conflicto', 409, 'CONFLICTO_IDEMPOTENCIA'],
    ['regla', 422, 'CAMPANIA_FINALIZADA'],
]);

it('responde 404 RECURSO_NO_ENCONTRADO en una ruta inexistente', function () {
    $this->getJson('/api/operaciones/v1/no-existe', tokenErrores())
        ->assertStatus(404)
        ->assertJson(['codigo' => 'RECURSO_NO_ENCONTRADO']);
});

it('responde 405 METODO_NO_PERMITIDO con un método no soportado', function () {
    $this->deleteJson('/api/operaciones/v1/prueba-errores', [], tokenErrores())
        ->assertStatus(405)
        ->assertJson(['codigo' => 'METODO_NO_PERMITIDO']);
});

it('responde 500 ERROR_INTERNO sin exponer el detalle', function () {
    $respuesta = $this->getJson('/api/operaciones/v1/prueba-errores/interno', tokenErrores())
        ->assertStatus(500)
        ->assertJson(['codigo' => 'ERROR_INTERNO', 'detalles' => []]);

    expect($respuesta->getContent())->not->toContain('detalle secreto');
});
