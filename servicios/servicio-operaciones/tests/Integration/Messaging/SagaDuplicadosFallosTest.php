<?php

use App\Domain\Saga\RepositorioSaga;
use App\Domain\Saga\Saga;
use App\Infrastructure\Messaging\TopologiaSaga;
use Tests\Support\DatosLabor;
use Tests\Support\FlujoSaga;
use Tests\Support\RabbitPruebas;

beforeEach(function () {
    $this->flujo = FlujoSaga::preparar($this);
});

describe('Historia 5 — duplicados y respuestas tardías', function () {
    it('un InsumosDescontados duplicado (mismo u otro idMensaje) no reenvía el costo y queda como tardío', function () {
        $flujo = $this->flujo->registrar()->descontado();
        $flujo->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');

        $flujo->descontado();
        $flujo->responder('InsumosDescontados', ['costoTotal' => '580.50'], idMensaje: DatosLabor::uuid());

        $saga = $flujo->saga();
        expect($saga['respuestasTardias'])->toHaveCount(2)
            ->and($saga['respuestasTardias'][0]['tipo'])->toBe('InsumosDescontados')
            ->and($saga['pasoActual'])->toBe('REGISTRAR_COSTO')
            ->and($flujo->labor()['estado'])->toBe('PENDIENTE');
        $flujo->sinComandos();
    });

    it('un CostoCampaniaRegistrado tardío durante la anulación no cambia la labor; decide la anulación', function () {
        $flujo = $this->flujo->registrar()->descontado();
        $flujo->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
        foreach ([31, 62, 93] as $segundos) {
            $flujo->vencer($segundos)->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
        }
        $flujo->vencer(124)->comandoA(TopologiaSaga::COLA_GESTION, 'AnularCostoCampania');

        $flujo->responder('CostoCampaniaRegistrado', ['idCampania' => $flujo->campania, 'idCosto' => 'c9', 'monto' => '580.50']);

        expect($flujo->estadoLabor())->toBe('PENDIENTE_REVISION/SIN_RESPUESTA_GESTION')
            ->and($flujo->saga())->toMatchArray(['estado' => 'COMPENSANDO', 'pasoActual' => 'ANULAR_COSTO'])
            ->and($flujo->saga()['respuestasTardias'][0]['tipo'])->toBe('CostoCampaniaRegistrado');

        $flujo->responder('CostoCampaniaAnulado', ['idCampania' => $flujo->campania, 'idCosto' => 'c9', 'sinEfecto' => false]);
        $flujo->comandoA(TopologiaSaga::COLA_INVENTARIO, 'RestaurarInsumos');
    });

    it('los rechazos SAGA_COMPENSADA y SAGA_ANULADA de pasos ya compensados se registran sin cambiar la labor', function () {
        $flujo = $this->flujo->registrar();
        foreach ([31, 62, 93] as $segundos) {
            $flujo->vencer($segundos)->comandoA(TopologiaSaga::COLA_INVENTARIO, 'DescontarInsumos');
        }
        $flujo->vencer(124)->comandoA(TopologiaSaga::COLA_INVENTARIO, 'RestaurarInsumos');

        $flujo->responder('InsumosRechazados', ['codigo' => 'SAGA_COMPENSADA', 'motivo' => 'Ya compensada.', 'insumosAfectados' => []]);
        $flujo->responder('CostoCampaniaRechazado', ['idCampania' => $flujo->campania, 'codigo' => 'SAGA_ANULADA', 'motivo' => 'Ya anulada.']);

        expect($flujo->estadoLabor())->toBe('PENDIENTE_REVISION/SIN_RESPUESTA_INVENTARIO')
            ->and(array_column($flujo->saga()['respuestasTardias'], 'codigo'))->toBe(['SAGA_COMPENSADA', 'SAGA_ANULADA']);
    });
});

describe('Historia 5 — fallos técnicos y mensajes no procesables', function () {
    it('si DynamoDB falla, reintenta 3 veces y manda el mensaje a la DLQ sin responder nada', function () {
        $flujo = $this->flujo->registrar();
        $repositorioQueFalla = new class implements RepositorioSaga
        {
            public int $lecturas = 0;

            public function buscar(string $idSaga): ?Saga
            {
                $this->lecturas++;
                throw new RuntimeException('DynamoDB no responde');
            }

            public function guardarNueva(Saga $saga): void {}

            public function actualizar(Saga $saga, int $versionLeida): void {}

            public function vencidas(DateTimeImmutable $ahora, int $maximo): array
            {
                return [];
            }
        };
        $this->app->instance(RepositorioSaga::class, $repositorioQueFalla);

        RabbitPruebas::responder('InsumosDescontados', $flujo->idSaga, ['idLabor' => $flujo->idLabor, 'costoTotal' => '1.00']);
        RabbitPruebas::procesarRespuestas(1);

        $dlq = RabbitPruebas::leer(TopologiaSaga::COLA_RESPUESTAS_DLQ);
        expect($repositorioQueFalla->lecturas)->toBe(4)
            ->and($dlq['tipo'])->toBe('InsumosDescontados')
            ->and($dlq['idCorrelacion'])->toBe($flujo->idSaga)
            ->and($dlq['_headers']['x-motivo'])->toContain('Fallo técnico tras 4 intentos')
            ->and(RabbitPruebas::contar(TopologiaSaga::COLA_RESPUESTAS))->toBe(0);
        $flujo->sinComandos();
    });

    it('un mensaje no procesable va a la DLQ sin reintentos y con su motivo', function (Closure $cuerpo, string $motivo) {
        $flujo = $this->flujo->registrar();

        RabbitPruebas::publicarCrudo($cuerpo($flujo));
        RabbitPruebas::procesarRespuestas(1);

        $dlq = RabbitPruebas::leer(TopologiaSaga::COLA_RESPUESTAS_DLQ);
        expect($dlq)->not->toBeNull()
            ->and($dlq['_headers']['x-motivo'])->toContain($motivo)
            ->and($dlq['_headers']['x-cola-origen'])->toBe(TopologiaSaga::COLA_RESPUESTAS)
            ->and($flujo->saga()['version'])->toBe(0);
    })->with([
        'JSON inválido' => [fn () => '{"tipo": ', 'no es un JSON'],
        'sin idMensaje' => [fn (FlujoSaga $f) => json_encode(['idCorrelacion' => $f->idSaga, 'tipo' => 'InsumosDescontados', 'datos' => []]), 'Falta idMensaje'],
        'tipo desconocido' => [fn (FlujoSaga $f) => json_encode(['idMensaje' => DatosLabor::uuid(), 'idCorrelacion' => $f->idSaga, 'tipo' => 'StockBajo', 'version' => 1, 'datos' => []]), 'Tipo de mensaje desconocido'],
        'versión 2' => [fn (FlujoSaga $f) => json_encode(['idMensaje' => DatosLabor::uuid(), 'idCorrelacion' => $f->idSaga, 'tipo' => 'InsumosDescontados', 'version' => 2, 'datos' => ['idSaga' => $f->idSaga, 'idLabor' => $f->idLabor, 'costoTotal' => '1.00']]), 'Versión'],
        'idSaga distinto de idCorrelacion' => [fn (FlujoSaga $f) => json_encode(['idMensaje' => DatosLabor::uuid(), 'idCorrelacion' => $f->idSaga, 'tipo' => 'InsumosDescontados', 'version' => 1, 'datos' => ['idSaga' => DatosLabor::uuid(), 'idLabor' => $f->idLabor, 'costoTotal' => '1.00']]), 'idCorrelacion distinto'],
        'Saga inexistente' => [function () {
            $otra = DatosLabor::uuid();

            return json_encode(['idMensaje' => DatosLabor::uuid(), 'idCorrelacion' => $otra, 'tipo' => 'CostoCampaniaRegistrado', 'version' => 1, 'datos' => ['idSaga' => $otra, 'idLabor' => DatosLabor::uuid()]]);
        }, 'no existe'],
        'costo como número JSON' => [fn (FlujoSaga $f) => json_encode(['idMensaje' => DatosLabor::uuid(), 'idCorrelacion' => $f->idSaga, 'tipo' => 'InsumosDescontados', 'version' => 1, 'datos' => ['idSaga' => $f->idSaga, 'idLabor' => $f->idLabor, 'costoTotal' => 580.5]]), 'costoTotal'],
    ]);
});
