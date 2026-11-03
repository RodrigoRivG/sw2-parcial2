<?php

use App\Infrastructure\Messaging\TopologiaSaga;
use Tests\Support\FlujoSaga;
use Tests\Support\RabbitPruebas;

beforeEach(function () {
    $this->flujo = FlujoSaga::preparar($this);
});

describe('Historia 2 — rechazo por stock', function () {
    it('InsumosRechazados deja la labor RECHAZADA con el código y los insumos afectados', function (string $codigo) {
        $flujo = $this->flujo->registrar('100');
        $afectados = [['idInsumo' => $flujo->descontar['datos']['items'][0]['idInsumo'], 'cantidadSolicitada' => '100.000', 'stockDisponible' => '2.000']];

        $flujo->responder('InsumosRechazados', ['codigo' => $codigo, 'motivo' => 'No hay stock suficiente.', 'insumosAfectados' => $afectados]);

        expect($flujo->labor())->toMatchArray([
            'estado' => 'RECHAZADA',
            'motivo' => ['codigo' => $codigo, 'mensaje' => 'No hay stock suficiente.', 'detalles' => $afectados],
        ])->and($flujo->saga()['estado'])->toBe('RECHAZADA');
        $flujo->sinComandos();
    })->with(['STOCK_INSUFICIENTE', 'INSUMO_NO_ENCONTRADO', 'DATOS_INVALIDOS']);
});

describe('Historia 3 — gestión rechaza o no responde', function () {
    it('CostoCampaniaRechazado → RestaurarInsumos y labor en revisión; InsumosRestaurados → COMPENSADA', function () {
        $flujo = $this->flujo->registrar()->descontado();
        $flujo->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');

        $flujo->responder('CostoCampaniaRechazado', ['idCampania' => $flujo->campania, 'codigo' => 'CAMPANIA_FINALIZADA', 'motivo' => 'La campaña está finalizada.']);

        $restaurar = $flujo->comandoA(TopologiaSaga::COLA_INVENTARIO, 'RestaurarInsumos');
        expect($restaurar['datos'])->toBe(['idSaga' => $flujo->idSaga, 'idLabor' => $flujo->idLabor])
            ->and($flujo->estadoLabor())->toBe('PENDIENTE_REVISION/COSTO_RECHAZADO')
            ->and($flujo->labor()['motivo']['detalles'])->toBe([['codigo' => 'CAMPANIA_FINALIZADA', 'motivo' => 'La campaña está finalizada.']])
            ->and($flujo->saga())->toMatchArray(['estado' => 'COMPENSANDO', 'pasoActual' => 'RESTAURAR_INSUMOS']);

        $flujo->responder('InsumosRestaurados', ['sinEfecto' => false, 'items' => []]);

        expect($flujo->saga()['estado'])->toBe('COMPENSADA')
            ->and($flujo->labor()['estado'])->toBe('PENDIENTE_REVISION');
        $flujo->sinComandos();
    });

    it('sin respuesta al costo: 4 envíos, luego AnularCostoCampania y recién después RestaurarInsumos', function () {
        $flujo = $this->flujo->registrar()->descontado();
        $flujo->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');

        // Escenario 3: reenvíos con el mismo idSaga y un idMensaje nuevo
        $ids = [];
        foreach ([31, 62, 93] as $segundos) {
            $reenvio = $flujo->vencer($segundos)->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
            $ids[] = $reenvio['idMensaje'];
        }
        expect(array_unique($ids))->toHaveCount(3)
            ->and($flujo->saga()['pasos'][1])->toMatchArray(['paso' => 'REGISTRAR_COSTO', 'intentos' => 4]);

        // Escenario 4: agotado → anulación, sin restaurar todavía
        $anular = $flujo->vencer(124)->comandoA(TopologiaSaga::COLA_GESTION, 'AnularCostoCampania');
        expect($anular['datos'])->toBe(['idSaga' => $flujo->idSaga, 'idLabor' => $flujo->idLabor, 'idCampania' => $flujo->campania])
            ->and($flujo->estadoLabor())->toBe('PENDIENTE_REVISION/SIN_RESPUESTA_GESTION')
            ->and(RabbitPruebas::contar(TopologiaSaga::COLA_INVENTARIO))->toBe(0);

        // Escenario 5
        $flujo->responder('CostoCampaniaAnulado', ['idCampania' => $flujo->campania, 'idCosto' => null, 'sinEfecto' => true]);
        $flujo->comandoA(TopologiaSaga::COLA_INVENTARIO, 'RestaurarInsumos');
        $flujo->responder('InsumosRestaurados', ['sinEfecto' => false, 'items' => []]);

        expect($flujo->saga()['estado'])->toBe('COMPENSADA');
        $flujo->sinComandos();
    });

    it('AnulacionCostoRechazada no restaura los insumos: REQUIERE_INTERVENCION (escenario 6)', function () {
        $flujo = $this->flujo->registrar()->descontado();
        $flujo->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
        foreach ([31, 62, 93] as $segundos) {
            $flujo->vencer($segundos)->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
        }
        $flujo->vencer(124)->comandoA(TopologiaSaga::COLA_GESTION, 'AnularCostoCampania');

        $flujo->responder('AnulacionCostoRechazada', ['idCampania' => $flujo->campania, 'idCosto' => 'c1', 'codigo' => 'CAMPANIA_FINALIZADA', 'motivo' => 'Finalizada.']);

        expect($flujo->saga()['estado'])->toBe('REQUIERE_INTERVENCION')
            ->and($flujo->estadoLabor())->toBe('PENDIENTE_REVISION/ANULACION_COSTO_RECHAZADA');
        $flujo->vencer(10_000);
        $flujo->sinComandos();
    });

    it('AnularCostoCampania sin respuesta se reenvía sin límite y nunca se restaura sin conocer el resultado (escenario 7)', function () {
        $flujo = $this->flujo->registrar()->descontado();
        $flujo->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
        foreach ([31, 62, 93] as $segundos) {
            $flujo->vencer($segundos)->comandoA(TopologiaSaga::COLA_GESTION, 'RegistrarCostoCampania');
        }
        $flujo->vencer(124)->comandoA(TopologiaSaga::COLA_GESTION, 'AnularCostoCampania');

        // Espera creciente: 30, 60, 120, 240, 480 s… desde el envío anterior
        $momento = 124;
        foreach ([30, 60, 120, 240, 480, 600] as $espera) {
            $momento += $espera + 1;
            $flujo->vencer($momento)->comandoA(TopologiaSaga::COLA_GESTION, 'AnularCostoCampania');
            expect(RabbitPruebas::contar(TopologiaSaga::COLA_INVENTARIO))->toBe(0);
        }

        expect($flujo->saga())->toMatchArray(['estado' => 'COMPENSANDO', 'pasoActual' => 'ANULAR_COSTO'])
            ->and($flujo->saga()['pasos'][2]['intentos'])->toBe(7);
    });
});

describe('Historia 4 — inventario no responde', function () {
    it('agotados los 4 envíos de DescontarInsumos, compensa con RestaurarInsumos', function () {
        $flujo = $this->flujo->registrar();
        foreach ([31, 62, 93] as $segundos) {
            $flujo->vencer($segundos)->comandoA(TopologiaSaga::COLA_INVENTARIO, 'DescontarInsumos');
        }

        $restaurar = $flujo->vencer(124)->comandoA(TopologiaSaga::COLA_INVENTARIO, 'RestaurarInsumos');
        expect($restaurar['datos'])->toBe(['idSaga' => $flujo->idSaga, 'idLabor' => $flujo->idLabor])
            ->and($flujo->estadoLabor())->toBe('PENDIENTE_REVISION/SIN_RESPUESTA_INVENTARIO');

        $flujo->responder('InsumosRestaurados', ['sinEfecto' => true, 'items' => []]);
        expect($flujo->saga()['estado'])->toBe('COMPENSADA');
        $flujo->sinComandos();
    });
});
