<?php

use App\InterfaceAdapters\Http\Middleware\IdCorrelacion;
use App\InterfaceAdapters\Http\Middleware\RequerirRol;
use App\InterfaceAdapters\Http\Middleware\ValidarJwt;
use App\InterfaceAdapters\Http\RenderizadorErrores;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Routing\Middleware\ThrottleRequests;
use Illuminate\Support\Facades\Route;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        api: __DIR__.'/../routes/api.php',
        apiPrefix: 'api/operaciones/v1',
        commands: __DIR__.'/../routes/console.php',
        then: function (): void {
            // Fuera del prefijo y sin token (constitución §9 y §11)
            Route::group([], __DIR__.'/../routes/publicas.php');
        },
    )
    ->withCommands([
        __DIR__.'/../app/InterfaceAdapters/Console',
        __DIR__.'/../app/Infrastructure/Persistence/DynamoDb/Console',
    ])
    ->withMiddleware(function (Middleware $middleware): void {
        $middleware->prepend(IdCorrelacion::class);
        $middleware->alias([
            'jwt' => ValidarJwt::class,
            'rol' => RequerirRol::class,
        ]);
        // Sin sesiones, cookies ni CSRF: la API solo acepta JWT
        $middleware->api(remove: [ThrottleRequests::class]);
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->shouldRenderJsonWhen(fn () => true);
        $exceptions->dontReportDuplicates();
        $exceptions->render(fn (Throwable $e) => RenderizadorErrores::renderizar($e));
    })->create();
