<?php

use App\Application\Contracts\PasarelaCampania;
use App\Application\Contracts\PublicacionFallida;
use App\Application\Contracts\PublicadorMensajes;
use App\Application\Contracts\Reloj;
use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborCasoUso;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborEntrada;
use App\Application\UseCases\Saga\ReanudarSagasEstancadas;
use App\Domain\FieldTask\CampaniaConsultada;
use App\Domain\FieldTask\TipoLabor;
use App\Domain\Saga\Participante;
use App\Infrastructure\Messaging\PublicadorRabbitMq;
use App\Infrastructure\Messaging\TopologiaSaga;
use App\InterfaceAdapters\Messaging\ConsumidorRespuestasSaga;
use App\InterfaceAdapters\Messaging\FuenteMensajes;
use Illuminate\Foundation\Application;
use Tests\Support\DatosLabor;
use Tests\Support\EnParalelo;
use Tests\Support\FlujoSaga;
use Tests\Support\RabbitPruebas;
use Tests\Support\RelojFijo;

beforeEach(function () {
    $this->flujo = FlujoSaga::preparar($this);
});

describe('Historia 6 — recuperación del coordinador', function () {
    it('si el broker no acepta la publicación, la labor se registra igual y la recuperación envía el comando (escenarios 1 y 4)', function () {
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
        $cuerpo = DatosLabor::realizada($this->flujo->parcela, $this->flujo->campania, ['insumos' => DatosLabor::insumos('5')]);

        $respuesta = $this->postJson('/api/operaciones/v1/labores', $cuerpo, $this->flujo->tecnico())
            ->assertCreated()->assertJson(['estado' => 'PENDIENTE']);
        expect(RabbitPruebas::contar(TopologiaSaga::COLA_INVENTARIO))->toBe(0);

        // El proceso "vuelve": publicador real y recuperación al vencer el tiempo límite
        $this->app->forgetInstance(PublicadorMensajes::class);
        $this->app->bind(PublicadorMensajes::class, PublicadorRabbitMq::class);
        $this->flujo->idSaga = (string) $respuesta->json('idSaga');
        $this->flujo->idLabor = $cuerpo['idOperacion'];
        $descontar = $this->flujo->vencer(31)->comandoA(TopologiaSaga::COLA_INVENTARIO, 'DescontarInsumos');

        expect($descontar['datos']['items'][0]['cantidad'])->toBe('5.000')
            ->and($this->flujo->saga()['pasos'][0]['intentos'])->toBe(2);
        $this->flujo->descontado();
        $this->flujo->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
    });

    it('con el consumidor detenido, las respuestas esperan en la cola y se procesan al volver (escenario 2)', function () {
        $sagas = [];
        foreach (range(1, 3) as $_) {
            $sagas[] = (clone $this->flujo)->registrar('1');
        }
        foreach ($sagas as $flujo) {
            RabbitPruebas::responder('InsumosDescontados', $flujo->idSaga, ['idLabor' => $flujo->idLabor, 'costoTotal' => '2.00']);
        }

        expect(RabbitPruebas::procesarRespuestas(3))->toBe(3);

        $registros = RabbitPruebas::leerTodos(TopologiaSaga::COLA_GESTION);
        expect(array_column($registros, 'tipo'))->toBe(['RegistrarCostoCampania', 'RegistrarCostoCampania', 'RegistrarCostoCampania'])
            ->and(array_column($registros, 'idCorrelacion'))->toEqualCanonicalizing(array_map(fn ($f) => $f->idSaga, $sagas));
    });

    it('dos ejecuciones simultáneas de la recuperación reenvían cada comando una sola vez (escenario 3)', function () {
        $flujo = $this->flujo->registrar('1');
        $ahora = DatosLabor::fecha('+31 seconds');

        $resultados = EnParalelo::ejecutar(2,
            fn (Application $app) => $app->make(ReanudarSagasEstancadas::class)->ejecutar(),
            fn (Application $app) => $app->instance(Reloj::class, new RelojFijo($ahora)));

        expect(array_sum(array_column($resultados, 'valor')))->toBe(1)
            ->and(RabbitPruebas::leerTodos(TopologiaSaga::COLA_INVENTARIO))->toHaveCount(1)
            ->and($flujo->saga()['pasos'][0]['intentos'])->toBe(2);
    });
});

describe('concurrencia', function () {
    it('50 labores con insumos registradas en paralelo terminan CONFIRMADA con un comando por Saga a cada participante (CE-SAG-03)', function () {
        $flujo = $this->flujo;
        $parcela = $flujo->parcela;
        $campania = $flujo->campania;
        $utc = new DateTimeZone('UTC');
        $creacion = new DateTimeImmutable(DatosLabor::fecha('-1 minute'), $utc);

        $resultados = EnParalelo::ejecutar(50, function (Application $app, int $i) use ($parcela, $campania, $creacion) {
            $resultado = $app->make(RegistrarLaborCasoUso::class)->ejecutar(
                new RegistrarLaborEntrada(DatosLabor::uuid(), $creacion, TipoLabor::FERTILIZACION, $parcela, $campania, $creacion, null,
                    [['idInsumo' => '8a1c0f3e-0000-4000-8000-000000000001', 'cantidad' => (string) ($i + 1)]]),
                new UsuarioAutenticado("tec-{$i}", 'Técnico', ['tecnico_campo']),
            );

            return [$resultado->labor->id, $resultado->labor->idSaga];
        }, fn (Application $app) => $app->instance(PasarelaCampania::class, new class($campania, $parcela) implements PasarelaCampania
        {
            public function __construct(private string $c, private string $p) {}

            public function consultar(string $idCampania): ?CampaniaConsultada
            {
                return new CampaniaConsultada($this->c, $this->p, 'EN_CURSO');
            }
        }));
        $sagas = array_column(array_column($resultados, 'valor'), 1, 0);
        expect($sagas)->toHaveCount(50);

        // Inventario: un DescontarInsumos por Saga; responde a todos
        $descuentos = RabbitPruebas::leerTodos(TopologiaSaga::COLA_INVENTARIO);
        expect(array_column($descuentos, 'idCorrelacion'))->toEqualCanonicalizing(array_values($sagas));
        foreach ($sagas as $idLabor => $idSaga) {
            RabbitPruebas::responder('InsumosDescontados', $idSaga, ['idLabor' => $idLabor, 'costoTotal' => '10.00']);
        }
        expect(RabbitPruebas::procesarRespuestas(50))->toBe(50);

        // Gestión: un RegistrarCostoCampania por Saga; responde a todos
        $costos = RabbitPruebas::leerTodos(TopologiaSaga::COLA_GESTION);
        expect(array_column($costos, 'idCorrelacion'))->toEqualCanonicalizing(array_values($sagas));
        foreach ($sagas as $idLabor => $idSaga) {
            RabbitPruebas::responder('CostoCampaniaRegistrado', $idSaga, ['idLabor' => $idLabor, 'idCampania' => $campania, 'idCosto' => DatosLabor::uuid(), 'monto' => '10.00'], origen: 'servicio-gestion');
        }
        expect(RabbitPruebas::procesarRespuestas(50))->toBe(50);

        $estados = [];
        foreach (array_keys($sagas) as $idLabor) {
            $estados[] = $this->getJson("/api/operaciones/v1/labores/{$idLabor}", $this->encabezados(['gerencia']))->json('estado');
        }
        expect(array_count_values($estados))->toBe(['CONFIRMADA' => 50]);
        $flujo->sinComandos();
    });

    it('respuesta y vencimiento simultáneos: o se confirma, o se anula el costo; nunca las dos cosas', function () {
        $flujo = $this->flujo->registrar('1')->descontado('3.00');
        $flujo->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
        foreach ([31, 62, 93] as $segundos) {
            $flujo->vencer($segundos)->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
        }
        RabbitPruebas::responder('CostoCampaniaRegistrado', $flujo->idSaga,
            ['idLabor' => $flujo->idLabor, 'idCampania' => $flujo->campania, 'idCosto' => 'c1', 'monto' => '3.00'], origen: 'servicio-gestion');
        $vencimiento = DatosLabor::fecha('+124 seconds');

        EnParalelo::ejecutar(2, function (Application $app, int $i) use ($vencimiento) {
            if ($i === 0) {
                $consumidor = $app->make(ConsumidorRespuestasSaga::class);

                return $app->make(FuenteMensajes::class)->consumir(fn (string $c) => $consumidor->manejar($c), 1, 2.0);
            }
            $app->instance(Reloj::class, new RelojFijo($vencimiento));

            return $app->make(ReanudarSagasEstancadas::class)->ejecutar();
        });

        $saga = $flujo->saga();
        $anulaciones = RabbitPruebas::leerTodos(TopologiaSaga::COLA_GESTION);
        if ($saga['estado'] === 'COMPLETADA') {
            expect($flujo->labor()['estado'])->toBe('CONFIRMADA')->and($anulaciones)->toBe([]);
        } else {
            expect($saga['estado'])->toBe('COMPENSANDO')
                ->and(array_column($anulaciones, 'tipo'))->toBe(['AnularCostoCampania'])
                ->and($saga['respuestasTardias'][0]['tipo'])->toBe('CostoCampaniaRegistrado')
                ->and($flujo->estadoLabor())->toBe('PENDIENTE_REVISION/SIN_RESPUESTA_GESTION');
        }
    });
});
