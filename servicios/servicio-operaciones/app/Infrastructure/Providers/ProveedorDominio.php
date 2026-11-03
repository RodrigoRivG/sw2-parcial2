<?php

namespace App\Infrastructure\Providers;

use App\Application\Contracts\ConsultaLabores;
use App\Application\Contracts\PasarelaCampania;
use App\Application\Contracts\PublicadorMensajes;
use App\Application\Contracts\RegistroAuditoria;
use App\Application\Contracts\Reloj;
use App\Application\Contracts\UnidadTrabajo;
use App\Domain\FieldTask\RepositorioLabor;
use App\Domain\Saga\ConfiguracionSaga;
use App\Domain\Saga\RepositorioSaga;
use App\Infrastructure\Clock\RelojSistema;
use App\Infrastructure\Http\ClienteServicioGestion;
use App\Infrastructure\Messaging\ComprobacionRabbitMq;
use App\Infrastructure\Messaging\ConexionRabbitMq;
use App\Infrastructure\Messaging\FuenteMensajesRabbitMq;
use App\Infrastructure\Messaging\PublicadorRabbitMq;
use App\Infrastructure\Persistence\DynamoDb\ComprobacionDynamoDb;
use App\Infrastructure\Persistence\DynamoDb\CreadorTablas;
use App\Infrastructure\Persistence\DynamoDb\NombresTablas;
use App\Infrastructure\Persistence\DynamoDb\RegistroAuditoriaDynamo;
use App\Infrastructure\Persistence\DynamoDb\RepositorioLaborDynamo;
use App\Infrastructure\Persistence\DynamoDb\RepositorioSagaDynamo;
use App\Infrastructure\Persistence\DynamoDb\UnidadTrabajoDynamo;
use App\Infrastructure\Security\ProveedorClavesJwksRemoto;
use App\InterfaceAdapters\Http\Controllers\SaludControlador;
use App\InterfaceAdapters\Http\Security\ProveedorClavesJwt;
use App\InterfaceAdapters\Messaging\ConsumidorRespuestasSaga;
use App\InterfaceAdapters\Messaging\FuenteMensajes;
use Aws\DynamoDb\DynamoDbClient;
use Illuminate\Support\ServiceProvider;

/**
 * Enlaza cada contrato de Application e InterfaceAdapters con su implementación de Infrastructure.
 */
final class ProveedorDominio extends ServiceProvider
{
    /** Comandos propios que necesitan el entorno completo (los de Laravel, como package:discover, no). */
    private const PREFIJOS_COMANDOS_PROPIOS = ['dynamodb:', 'labores:', 'sagas:', 'incidencias:', 'operaciones:', 'schedule:'];

    public function register(): void
    {
        $this->app->singleton(DynamoDbClient::class, function () {
            $configuracion = [
                'region' => config('aws.region'),
                'version' => '2012-08-10',
                'http' => ['connect_timeout' => 2, 'timeout' => 10],
            ];
            if (config('aws.dynamodb.endpoint')) {
                $configuracion['endpoint'] = config('aws.dynamodb.endpoint');
            }
            if (config('aws.clave')) {
                $configuracion['credentials'] = ['key' => config('aws.clave'), 'secret' => config('aws.secreto')];
            }

            return new DynamoDbClient($configuracion);
        });

        $this->app->singleton(NombresTablas::class, fn () => new NombresTablas((string) config('aws.dynamodb.prefijo_tablas')));
        $this->app->singleton(UnidadTrabajoDynamo::class);
        $this->app->bind(UnidadTrabajo::class, UnidadTrabajoDynamo::class);
        $this->app->bind(RegistroAuditoria::class, RegistroAuditoriaDynamo::class);
        $this->app->singleton(Reloj::class, RelojSistema::class);
        $this->app->bind(CreadorTablas::class, fn ($app) => new CreadorTablas(
            $app->make(DynamoDbClient::class),
            $app->make(NombresTablas::class),
            database_path('dynamodb/tablas.json'),
        ));
        $this->app->singleton(ProveedorClavesJwt::class, ProveedorClavesJwksRemoto::class);

        // Labores (spec-labores.md)
        $this->app->bind(RepositorioLabor::class, RepositorioLaborDynamo::class);
        $this->app->bind(ConsultaLabores::class, RepositorioLaborDynamo::class);
        $this->app->bind(PasarelaCampania::class, ClienteServicioGestion::class);

        // Saga (spec-saga.md)
        $this->app->bind(RepositorioSaga::class, RepositorioSagaDynamo::class);
        $this->app->singleton(ConexionRabbitMq::class);
        $this->app->bind(PublicadorMensajes::class, PublicadorRabbitMq::class);
        $this->app->bind(FuenteMensajes::class, FuenteMensajesRabbitMq::class);
        $this->app->bind(ConfiguracionSaga::class, fn () => new ConfiguracionSaga(
            (int) config('saga.tiempo_limite_segundos'),
            (int) config('saga.maximo_envios'),
            (int) config('saga.espera_maxima_compensacion_segundos'),
        ));
        $this->app->when(ConsumidorRespuestasSaga::class)->needs('$esperasMs')->give(fn () => config('rabbitmq.esperas_reintento_ms'));
        ValidadorEntorno::exigir('RABBITMQ_HOST', 'RABBITMQ_USER', 'RABBITMQ_PASSWORD');

        $this->app->tag([ComprobacionDynamoDb::class, ComprobacionRabbitMq::class], 'comprobaciones_salud');
        $this->app->when(SaludControlador::class)->needs('$comprobaciones')->giveTagged('comprobaciones_salud');
    }

    public function boot(): void
    {
        if (! $this->app->runningInConsole() || $this->esComandoPropio()) {
            ValidadorEntorno::validar();
        }
    }

    private function esComandoPropio(): bool
    {
        $comando = (string) ($_SERVER['argv'][1] ?? '');
        foreach (self::PREFIJOS_COMANDOS_PROPIOS as $prefijo) {
            if (str_starts_with($comando, $prefijo)) {
                return true;
            }
        }

        return false;
    }
}
