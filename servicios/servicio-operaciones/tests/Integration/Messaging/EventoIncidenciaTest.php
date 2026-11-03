<?php

use App\Application\Contracts\PublicacionFallida;
use App\Application\Contracts\PublicadorMensajes;
use App\Application\Contracts\Reloj;
use App\Domain\Saga\Participante;
use App\Infrastructure\Messaging\PublicadorRabbitMq;
use App\Infrastructure\Messaging\TopologiaSaga;
use Tests\Support\DatosIncidencia;
use Tests\Support\DatosLabor;
use Tests\Support\RabbitPruebas;
use Tests\Support\RelojFijo;

const COLA_N8N_PRUEBAS = 'pruebas.n8n.incidencias';

beforeEach(function () {
    // Una cola como la que crea n8n, enlazada al exchange eventos (constitución §10)
    $canal = RabbitPruebas::canal();
    $canal->queue_declare(COLA_N8N_PRUEBAS, false, true, false, false);
    $canal->queue_bind(COLA_N8N_PRUEBAS, TopologiaSaga::EXCHANGE_EVENTOS, 'operaciones.incidencia.registrada');
    $canal->queue_purge(COLA_N8N_PRUEBAS);
    $this->parcela = DatosLabor::uuid();
    $this->tecnico = $this->encabezados(['tecnico_campo'], 'tec-ana');
});

it('publica IncidenciaRegistrada con el sobre común y los datos para n8n (escenario 1)', function () {
    $campania = DatosLabor::uuid();
    $datos = DatosIncidencia::datos($this->parcela, ['idCampania' => $campania, 'tipo' => 'ENFERMEDAD', 'clasificacion' => [
        'categoria' => 'tizón', 'confianza' => '0.91', 'versionModelo' => 'v2', 'origen' => 'SERVIDOR',
    ]]);

    DatosIncidencia::enviar($this, $datos, DatosIncidencia::jpeg(), [...$this->tecnico, 'X-Correlation-Id' => 'corr-incidencia-1'])->assertCreated();

    $evento = RabbitPruebas::leer(COLA_N8N_PRUEBAS);
    expect($evento)->toMatchArray([
        'tipo' => 'IncidenciaRegistrada',
        'version' => 1,
        'origen' => 'servicio-operaciones',
        'idCorrelacion' => 'corr-incidencia-1',
    ])->and($evento['datos'])->toBe([
        'idIncidencia' => $datos['idOperacion'],
        'tipo' => 'ENFERMEDAD',
        'descripcion' => $datos['descripcion'],
        'idParcela' => $this->parcela,
        'idCampania' => $campania,
        'fechaObservacion' => $datos['fechaObservacion'],
        'registradaPor' => ['id' => 'tec-ana', 'nombre' => 'Usuario tec-ana'],
        'clasificacion' => ['categoria' => 'tizón', 'confianza' => '0.9100', 'versionModelo' => 'v2', 'origen' => 'SERVIDOR'],
    ]);
});

it('si RabbitMQ falla, la incidencia se registra igual y la tarea la republica cuando vuelve (escenarios 2 y 3)', function () {
    $this->app->instance(PublicadorMensajes::class, new class implements PublicadorMensajes
    {
        public function enviarComando(Participante $destino, string $tipo, array $datos, string $idCorrelacion): string
        {
            throw new PublicacionFallida('RabbitMQ no disponible');
        }

        public function publicarEvento(string $routingKey, string $tipo, array $datos, string $idCorrelacion): string
        {
            throw new PublicacionFallida('RabbitMQ no disponible');
        }
    });
    $datos = DatosIncidencia::datos($this->parcela);
    DatosIncidencia::enviar($this, $datos, DatosIncidencia::jpeg(), $this->tecnico)->assertCreated();
    expect(RabbitPruebas::contar(COLA_N8N_PRUEBAS))->toBe(0);

    // RabbitMQ vuelve. Antes de 1 minuto no se republica (la solicitud podría estar publicándola)
    $this->app->forgetInstance(PublicadorMensajes::class);
    $this->app->bind(PublicadorMensajes::class, PublicadorRabbitMq::class);
    $this->artisan('incidencias:republicar-eventos')->assertSuccessful();
    expect(RabbitPruebas::contar(COLA_N8N_PRUEBAS))->toBe(0);

    $this->app->instance(Reloj::class, new RelojFijo(DatosLabor::fecha('+61 seconds')));
    $this->artisan('incidencias:republicar-eventos')->assertSuccessful();
    $this->artisan('incidencias:republicar-eventos')->assertSuccessful();

    // La tarea republica todas las pendientes de la tabla (también las de otros tests): se cuenta la de este
    $ids = array_column(array_column(RabbitPruebas::leerTodos(COLA_N8N_PRUEBAS), 'datos'), 'idIncidencia');
    expect(array_count_values($ids)[$datos['idOperacion']] ?? 0)->toBe(1);
});

it('una incidencia repetida no publica otro evento (escenario 4)', function () {
    $datos = DatosIncidencia::datos($this->parcela);
    $foto = DatosIncidencia::jpeg();

    DatosIncidencia::enviar($this, $datos, $foto, $this->tecnico)->assertCreated();
    DatosIncidencia::enviar($this, $datos, $foto, $this->tecnico)->assertOk();

    expect(RabbitPruebas::leerTodos(COLA_N8N_PRUEBAS))->toHaveCount(1);
});
