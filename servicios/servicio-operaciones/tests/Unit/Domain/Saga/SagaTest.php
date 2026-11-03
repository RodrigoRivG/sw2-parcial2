<?php

use App\Domain\FieldTask\ConsumoInsumo;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\Responsable;
use App\Domain\FieldTask\TipoLabor;
use App\Domain\FieldTask\ValidacionCampania;
use App\Domain\Saga\ConfiguracionSaga;
use App\Domain\Saga\Decision;
use App\Domain\Saga\EstadoPaso;
use App\Domain\Saga\EstadoSaga;
use App\Domain\Saga\PasoSaga;
use App\Domain\Saga\RespuestaSaga;
use App\Domain\Saga\Saga;
use App\Domain\Saga\TipoRespuesta;
use App\Domain\Shared\Cantidad;

function momento(string $hora = '14:00:00'): DateTimeImmutable
{
    return new DateTimeImmutable("2026-11-02T{$hora}Z", new DateTimeZone('UTC'));
}

function configuracion(): ConfiguracionSaga
{
    return new ConfiguracionSaga(tiempoLimiteSegundos: 30, maximoEnvios: 4, esperaMaximaCompensacionSegundos: 600);
}

function sagaNueva(): Saga
{
    $labor = LaborAgricola::registrarRealizada('l1', 'h', TipoLabor::FERTILIZACION, 'p1', 'c1', momento('13:00:00'), momento('13:00:00'), null,
        [new ConsumoInsumo('i1', Cantidad::desdeTexto('100'))], new Responsable('tec', 'Ana'), ValidacionCampania::VALIDADA, momento());

    return Saga::iniciar('s1', $labor, momento(), configuracion());
}

function respuesta(TipoRespuesta $tipo, array $campos = []): RespuestaSaga
{
    return new RespuestaSaga($tipo, $campos['idMensaje'] ?? 'm-'.uniqid(), $campos['codigo'] ?? null, $campos['motivo'] ?? null,
        $campos['costoTotal'] ?? null, $campos['detalles'] ?? []);
}

/** Lleva la Saga hasta REGISTRAR_COSTO enviado. */
function sagaEnCosto(): Saga
{
    $saga = sagaNueva();
    $saga->aplicarRespuesta(respuesta(TipoRespuesta::INSUMOS_DESCONTADOS, ['costoTotal' => '580.50']), momento('14:00:01'), configuracion());

    return $saga;
}

/** Vence el paso actual hasta agotar los envíos hacia adelante. */
function agotar(Saga $saga): Decision
{
    $hora = momento('14:00:00');
    for ($i = 0; $i < 4; $i++) {
        $hora = $hora->modify('+31 seconds');
        $decision = $saga->vencer($hora, configuracion());
    }

    return $decision;
}

describe('inicio (RQ-SAG-01)', function () {
    it('empieza EN_CURSO con DESCONTAR_INSUMOS enviado y la fecha límite a 30 s', function () {
        $saga = sagaNueva();

        expect($saga->estado)->toBe(EstadoSaga::EN_CURSO)
            ->and($saga->pasoActual)->toBe(PasoSaga::DESCONTAR_INSUMOS)
            ->and($saga->paso(PasoSaga::DESCONTAR_INSUMOS)->estado)->toBe(EstadoPaso::ENVIADO)
            ->and($saga->paso(PasoSaga::DESCONTAR_INSUMOS)->intentos)->toBe(1)
            ->and($saga->fechaLimite)->toEqual(momento('14:00:30'))
            ->and($saga->version)->toBe(0);
    });
});

describe('respuestas (RQ-SAG-04)', function () {
    it('InsumosDescontados con costo > 0 guarda el costo y envía RegistrarCostoCampania', function () {
        $saga = sagaNueva();
        $decision = $saga->aplicarRespuesta(respuesta(TipoRespuesta::INSUMOS_DESCONTADOS, ['costoTotal' => '580.50']), momento('14:00:05'), configuracion());

        expect($decision->pasoAEnviar)->toBe(PasoSaga::REGISTRAR_COSTO)
            ->and($decision->cambiaLabor())->toBeFalse()
            ->and($saga->costoTotal)->toBe('580.50')
            ->and($saga->paso(PasoSaga::DESCONTAR_INSUMOS)->estado)->toBe(EstadoPaso::COMPLETADO)
            ->and($saga->paso(PasoSaga::REGISTRAR_COSTO)->estado)->toBe(EstadoPaso::ENVIADO)
            ->and($saga->fechaLimite)->toEqual(momento('14:00:35'))
            ->and($saga->version)->toBe(1);
    });

    it('InsumosDescontados con "0.00" completa la Saga sin registrar costo', function () {
        $saga = sagaNueva();
        $decision = $saga->aplicarRespuesta(respuesta(TipoRespuesta::INSUMOS_DESCONTADOS, ['costoTotal' => '0.00']), momento('14:00:05'), configuracion());

        expect($decision->pasoAEnviar)->toBeNull()
            ->and($decision->estadoLabor)->toBe(EstadoLabor::CONFIRMADA)
            ->and($saga->estado)->toBe(EstadoSaga::COMPLETADA)
            ->and($saga->paso(PasoSaga::REGISTRAR_COSTO)->estado)->toBe(EstadoPaso::OMITIDO);
    });

    it('InsumosRechazados rechaza la Saga y la labor con el código e insumos afectados', function () {
        $saga = sagaNueva();
        $afectados = [['idInsumo' => 'i1', 'cantidadSolicitada' => '100.000', 'stockDisponible' => '2.000']];
        $decision = $saga->aplicarRespuesta(respuesta(TipoRespuesta::INSUMOS_RECHAZADOS, [
            'codigo' => 'STOCK_INSUFICIENTE', 'motivo' => 'No alcanza', 'detalles' => $afectados,
        ]), momento('14:00:05'), configuracion());

        expect($saga->estado)->toBe(EstadoSaga::RECHAZADA)
            ->and($saga->paso(PasoSaga::DESCONTAR_INSUMOS)->estado)->toBe(EstadoPaso::RECHAZADO)
            ->and($saga->paso(PasoSaga::DESCONTAR_INSUMOS)->respuesta)->toBe(['tipo' => 'InsumosRechazados', 'codigo' => 'STOCK_INSUFICIENTE', 'motivo' => 'No alcanza'])
            ->and($decision->estadoLabor)->toBe(EstadoLabor::RECHAZADA)
            ->and($decision->motivoLabor?->codigo)->toBe('STOCK_INSUFICIENTE')
            ->and($decision->motivoLabor?->detalles)->toBe($afectados)
            ->and($decision->pasoAEnviar)->toBeNull();
    });

    it('CostoCampaniaRegistrado completa la Saga y confirma la labor', function () {
        $saga = sagaEnCosto();
        $decision = $saga->aplicarRespuesta(respuesta(TipoRespuesta::COSTO_REGISTRADO), momento('14:00:06'), configuracion());

        expect($saga->estado)->toBe(EstadoSaga::COMPLETADA)
            ->and($decision->estadoLabor)->toBe(EstadoLabor::CONFIRMADA);
    });

    it('CostoCampaniaRechazado compensa restaurando insumos y deja la labor en revisión', function () {
        $saga = sagaEnCosto();
        $decision = $saga->aplicarRespuesta(respuesta(TipoRespuesta::COSTO_RECHAZADO, ['codigo' => 'CAMPANIA_FINALIZADA', 'motivo' => 'Finalizada']), momento('14:00:06'), configuracion());

        expect($saga->estado)->toBe(EstadoSaga::COMPENSANDO)
            ->and($decision->pasoAEnviar)->toBe(PasoSaga::RESTAURAR_INSUMOS)
            ->and($decision->estadoLabor)->toBe(EstadoLabor::PENDIENTE_REVISION)
            ->and($decision->motivoLabor?->codigo)->toBe('COSTO_RECHAZADO')
            ->and($decision->motivoLabor?->detalles)->toBe([['codigo' => 'CAMPANIA_FINALIZADA', 'motivo' => 'Finalizada']]);
    });

    it('InsumosRestaurados termina la compensación', function () {
        $saga = sagaEnCosto();
        $saga->aplicarRespuesta(respuesta(TipoRespuesta::COSTO_RECHAZADO, ['codigo' => 'X', 'motivo' => 'Y']), momento('14:00:06'), configuracion());
        $decision = $saga->aplicarRespuesta(respuesta(TipoRespuesta::INSUMOS_RESTAURADOS), momento('14:00:07'), configuracion());

        expect($saga->estado)->toBe(EstadoSaga::COMPENSADA)
            ->and($decision->cambiaLabor())->toBeFalse()
            ->and($decision->pasoAEnviar)->toBeNull();
    });

    it('CostoCampaniaAnulado envía RestaurarInsumos', function () {
        $saga = sagaEnCosto();
        agotar($saga);
        $decision = $saga->aplicarRespuesta(respuesta(TipoRespuesta::COSTO_ANULADO), momento('14:05:00'), configuracion());

        expect($decision->pasoAEnviar)->toBe(PasoSaga::RESTAURAR_INSUMOS)
            ->and($saga->estado)->toBe(EstadoSaga::COMPENSANDO)
            ->and($saga->paso(PasoSaga::ANULAR_COSTO)->estado)->toBe(EstadoPaso::COMPLETADO);
    });

    it('AnulacionCostoRechazada no restaura: REQUIERE_INTERVENCION y solo cambia el motivo de la labor', function () {
        $saga = sagaEnCosto();
        agotar($saga);
        $decision = $saga->aplicarRespuesta(respuesta(TipoRespuesta::ANULACION_RECHAZADA, ['codigo' => 'CAMPANIA_FINALIZADA', 'motivo' => 'Ya finalizada']), momento('14:05:00'), configuracion());

        expect($saga->estado)->toBe(EstadoSaga::REQUIERE_INTERVENCION)
            ->and($decision->pasoAEnviar)->toBeNull()
            ->and($decision->estadoLabor)->toBeNull()
            ->and($decision->motivoLabor?->codigo)->toBe('ANULACION_COSTO_RECHAZADA')
            ->and($saga->pasos)->not->toHaveKey(PasoSaga::RESTAURAR_INSUMOS->value);
    });
});

describe('respuestas tardías y duplicadas (Historia 5)', function () {
    it('un InsumosDescontados repetido se registra como tardío sin reenviar nada', function () {
        $saga = sagaEnCosto();
        $decision = $saga->aplicarRespuesta(respuesta(TipoRespuesta::INSUMOS_DESCONTADOS, ['costoTotal' => '580.50', 'idMensaje' => 'dup']), momento('14:00:09'), configuracion());

        expect($decision->tardia)->toBeTrue()
            ->and($decision->pasoAEnviar)->toBeNull()
            ->and($decision->cambiaLabor())->toBeFalse()
            ->and($saga->pasoActual)->toBe(PasoSaga::REGISTRAR_COSTO)
            ->and($saga->respuestasTardias[0])->toMatchArray(['tipo' => 'InsumosDescontados', 'idMensaje' => 'dup']);
    });

    it('un CostoCampaniaRegistrado tardío durante la anulación no cambia nada', function () {
        $saga = sagaEnCosto();
        agotar($saga);
        $decision = $saga->aplicarRespuesta(respuesta(TipoRespuesta::COSTO_REGISTRADO), momento('14:05:00'), configuracion());

        expect($decision->tardia)->toBeTrue()->and($saga->pasoActual)->toBe(PasoSaga::ANULAR_COSTO)->and($saga->estado)->toBe(EstadoSaga::COMPENSANDO);
    });

    it('cualquier respuesta a una Saga terminada es tardía', function (TipoRespuesta $tipo) {
        $saga = sagaEnCosto();
        $saga->aplicarRespuesta(respuesta(TipoRespuesta::COSTO_REGISTRADO), momento('14:00:06'), configuracion());

        expect($saga->aplicarRespuesta(respuesta($tipo, ['codigo' => 'SAGA_ANULADA', 'motivo' => 'x']), momento('14:00:07'), configuracion())->tardia)->toBeTrue()
            ->and($saga->estado)->toBe(EstadoSaga::COMPLETADA);
    })->with(TipoRespuesta::cases());

    it('conserva solo las 20 respuestas tardías más recientes', function () {
        $saga = sagaEnCosto();
        foreach (range(1, 25) as $i) {
            $saga->aplicarRespuesta(respuesta(TipoRespuesta::INSUMOS_DESCONTADOS, ['costoTotal' => '1.00', 'idMensaje' => "m{$i}"]), momento('14:00:10'), configuracion());
        }

        expect($saga->respuestasTardias)->toHaveCount(20)
            ->and($saga->respuestasTardias[0]['idMensaje'])->toBe('m6')
            ->and($saga->respuestasTardias[19]['idMensaje'])->toBe('m25');
    });
});

describe('vencimientos (RQ-SAG-05)', function () {
    it('no hace nada antes de la fecha límite', function () {
        $saga = sagaNueva();
        $decision = $saga->vencer(momento('14:00:29'), configuracion());

        expect($decision->pasoAEnviar)->toBeNull()->and($saga->version)->toBe(0);
    });

    it('reenvía el paso hacia adelante hasta 4 envíos con el mismo tiempo límite', function () {
        $saga = sagaNueva();
        $hora = momento();
        foreach ([2, 3, 4] as $envio) {
            $hora = $hora->modify('+30 seconds');
            $decision = $saga->vencer($hora, configuracion());
            expect($decision->pasoAEnviar)->toBe(PasoSaga::DESCONTAR_INSUMOS)
                ->and($saga->paso(PasoSaga::DESCONTAR_INSUMOS)->intentos)->toBe($envio)
                ->and($saga->fechaLimite)->toEqual($hora->modify('+30 seconds'));
        }
    });

    it('agotado DESCONTAR_INSUMOS, compensa con RestaurarInsumos y labor en revisión (SIN_RESPUESTA_INVENTARIO)', function () {
        $saga = sagaNueva();
        $decision = agotar($saga);

        expect($decision->pasoAEnviar)->toBe(PasoSaga::RESTAURAR_INSUMOS)
            ->and($decision->estadoLabor)->toBe(EstadoLabor::PENDIENTE_REVISION)
            ->and($decision->motivoLabor?->codigo)->toBe('SIN_RESPUESTA_INVENTARIO')
            ->and($saga->estado)->toBe(EstadoSaga::COMPENSANDO)
            ->and($saga->paso(PasoSaga::DESCONTAR_INSUMOS)->estado)->toBe(EstadoPaso::SIN_RESPUESTA)
            ->and($saga->paso(PasoSaga::DESCONTAR_INSUMOS)->error)->toContain('4 envíos');
    });

    it('agotado REGISTRAR_COSTO, primero anula el costo y no restaura todavía (SIN_RESPUESTA_GESTION)', function () {
        $saga = sagaEnCosto();
        $decision = agotar($saga);

        expect($decision->pasoAEnviar)->toBe(PasoSaga::ANULAR_COSTO)
            ->and($decision->motivoLabor?->codigo)->toBe('SIN_RESPUESTA_GESTION')
            ->and($saga->pasos)->not->toHaveKey(PasoSaga::RESTAURAR_INSUMOS->value);
    });

    it('las compensaciones se reenvían sin límite con espera que se duplica hasta 10 minutos', function () {
        $saga = sagaEnCosto();
        agotar($saga);
        $esperas = [];
        $hora = $saga->fechaLimite;
        foreach (range(1, 8) as $_) {
            $decision = $saga->vencer($hora, configuracion());
            expect($decision->pasoAEnviar)->toBe(PasoSaga::ANULAR_COSTO);
            $esperas[] = $saga->fechaLimite->getTimestamp() - $hora->getTimestamp();
            $hora = $saga->fechaLimite;
        }

        expect($esperas)->toBe([60, 120, 240, 480, 600, 600, 600, 600])
            ->and($saga->paso(PasoSaga::ANULAR_COSTO)->intentos)->toBe(9)
            ->and($saga->estado)->toBe(EstadoSaga::COMPENSANDO);
    });

    it('una Saga terminada no vence', function () {
        $saga = sagaEnCosto();
        $saga->aplicarRespuesta(respuesta(TipoRespuesta::COSTO_REGISTRADO), momento('14:00:06'), configuracion());

        expect($saga->estaVencida(momento('15:00:00')))->toBeFalse()
            ->and($saga->vencer(momento('15:00:00'), configuracion())->pasoAEnviar)->toBeNull();
    });
});

it('clonar una Saga copia sus pasos', function () {
    $saga = sagaNueva();
    $copia = clone $saga;
    $copia->vencer(momento('14:01:00'), configuracion());

    expect($saga->paso(PasoSaga::DESCONTAR_INSUMOS)->intentos)->toBe(1);
});
