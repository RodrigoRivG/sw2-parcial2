<?php

namespace Tests;

use App\InterfaceAdapters\Http\Security\ProveedorClavesJwt;
use Illuminate\Foundation\Testing\TestCase as BaseTestCase;
use Illuminate\Support\Facades\Http;
use Tests\Support\Tokens;

abstract class TestCase extends BaseTestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        $this->app->singleton(ProveedorClavesJwt::class, Tokens::class);
        // Ninguna llamada HTTP real a Keycloak o al Gateway: cada test simula las que necesita
        Http::preventStrayRequests();
    }

    /**
     * @param  list<string>  $roles
     * @return array<string, string>
     */
    protected function encabezados(array $roles, string $sub = 'usuario-pruebas'): array
    {
        return ['Authorization' => 'Bearer '.Tokens::para($roles, $sub), 'Accept' => 'application/json'];
    }
}
