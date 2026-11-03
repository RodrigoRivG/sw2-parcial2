<?php

use App\Domain\FieldTask\CampaniaConsultada;
use App\Domain\FieldTask\ConsumoInsumo;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\Responsable;
use App\Domain\FieldTask\TipoLabor;
use App\Domain\FieldTask\ValidacionCampania;
use App\Domain\Shared\Cantidad;
use App\Domain\Shared\ExcepcionDominio;

function utc(string $fecha): DateTimeImmutable
{
    return new DateTimeImmutable($fecha, new DateTimeZone('UTC'));
}

function laborProgramada(ValidacionCampania $validacion = ValidacionCampania::VALIDADA, string $fecha = '2026-11-20'): LaborAgricola
{
    return LaborAgricola::programar(
        'l1', 'h1', TipoLabor::FERTILIZACION, 'p1', 'c1', $fecha, utc('2026-11-02T13:00:00Z'), ' Al voleo ',
        new Responsable('admin-1', 'Luis'), $validacion, utc('2026-11-02T14:00:00Z'),
    );
}

/** @param list<ConsumoInsumo> $insumos */
function laborRealizada(array $insumos = [], ValidacionCampania $validacion = ValidacionCampania::VALIDADA): LaborAgricola
{
    return LaborAgricola::registrarRealizada(
        'l2', 'h2', TipoLabor::RIEGO, 'p1', 'c1', utc('2026-11-02T13:30:00Z'), utc('2026-11-02T13:58:00Z'), null, $insumos,
        new Responsable('tec-1', 'Ana'), $validacion, utc('2026-11-02T14:00:00Z'),
    );
}

function urea(string $cantidad = '100'): ConsumoInsumo
{
    return new ConsumoInsumo('i1', Cantidad::desdeTexto($cantidad));
}

function codigoDe(callable $accion): string
{
    try {
        $accion();
    } catch (ExcepcionDominio $e) {
        return $e->codigo;
    }

    return 'SIN_ERROR';
}

describe('estado inicial (RQ-LAB-06)', function () {
    it('programada queda PROGRAMADA, sin insumos, con programadaPor y observaciones recortadas', function () {
        $labor = laborProgramada();

        expect($labor->estado)->toBe(EstadoLabor::PROGRAMADA)
            ->and($labor->insumos)->toBe([])
            ->and($labor->programadaPor?->id)->toBe('admin-1')
            ->and($labor->observaciones)->toBe('Al voleo')
            ->and($labor->fechaReferencia())->toBe('2026-11-20')
            ->and($labor->version)->toBe(0);
    });

    it('realizada sin insumos queda CONFIRMADA', function () {
        expect(laborRealizada()->estado)->toBe(EstadoLabor::CONFIRMADA);
    });

    it('realizada con insumos queda PENDIENTE', function () {
        $labor = laborRealizada([urea()]);

        expect($labor->estado)->toBe(EstadoLabor::PENDIENTE)
            ->and($labor->fechaReferencia())->toBe('2026-11-02T13:30:00Z')
            ->and($labor->fechaRecepcionEjecucion)->toEqual(utc('2026-11-02T14:00:00Z'));
    });

    it('con la validación diferida queda PENDIENTE y con el próximo intento a 1 minuto', function (Closure $crear) {
        $labor = $crear();

        expect($labor->estado)->toBe(EstadoLabor::PENDIENTE)
            ->and($labor->validacionPendiente())->toBeTrue()
            ->and($labor->fechaProximoValidacion)->toEqual(utc('2026-11-02T14:01:00Z'));
    })->with([
        'programada' => fn () => laborProgramada(ValidacionCampania::PENDIENTE),
        'realizada' => fn () => laborRealizada([], ValidacionCampania::PENDIENTE),
    ]);
});

describe('fechas (RQ-LAB-03)', function () {
    it('rechaza una fecha programada anterior al día de creación', function () {
        expect(codigoDe(fn () => laborProgramada(fecha: '2026-11-01')))->toBe('FECHA_PROGRAMADA_INVALIDA');
    });

    it('acepta la fecha programada del mismo día de la creación', function () {
        expect(laborProgramada(fecha: '2026-11-02')->estado)->toBe(EstadoLabor::PROGRAMADA);
    });

    it('rechaza la creación en el futuro más allá de la tolerancia', function () {
        expect(codigoDe(fn () => LaborAgricola::validarProgramacion('2026-11-20', utc('2026-11-02T14:06:00Z'), utc('2026-11-02T14:00:00Z'))))
            ->toBe('FECHA_PROGRAMADA_INVALIDA')
            ->and(codigoDe(fn () => LaborAgricola::validarEjecucion(utc('2026-11-02T13:00:00Z'), utc('2026-11-02T14:06:00Z'), utc('2026-11-02T14:00:00Z'))))
            ->toBe('FECHA_EJECUCION_INVALIDA');
    });

    it('acepta la ejecución dentro de los 5 minutos de tolerancia y la rechaza después', function () {
        $ahora = utc('2026-11-02T14:00:00Z');

        expect(codigoDe(fn () => LaborAgricola::validarEjecucion(utc('2026-11-02T14:05:00Z'), $ahora, $ahora)))->toBe('SIN_ERROR')
            ->and(codigoDe(fn () => LaborAgricola::validarEjecucion(utc('2026-11-02T14:05:01Z'), $ahora, $ahora)))->toBe('FECHA_EJECUCION_INVALIDA');
    });
});

describe('realización (RQ-LAB-07)', function () {
    it('pasa a PENDIENTE con insumos, cambia el responsable y conserva programadaPor y fechaProgramada', function () {
        $labor = laborProgramada();

        $labor->realizar('op2', 'h-real', utc('2026-11-20T10:00:00Z'), utc('2026-11-20T10:05:00Z'), null, [urea()],
            new Responsable('tec-1', 'Ana'), ValidacionCampania::VALIDADA, utc('2026-11-20T10:06:00Z'));

        expect($labor->estado)->toBe(EstadoLabor::PENDIENTE)
            ->and($labor->responsable->id)->toBe('tec-1')
            ->and($labor->programadaPor?->id)->toBe('admin-1')
            ->and($labor->fechaProgramada)->toBe('2026-11-20')
            ->and($labor->observaciones)->toBe('Al voleo')
            ->and($labor->fechaReferencia())->toBe('2026-11-20T10:00:00Z')
            ->and($labor->idOperacionRealizacion)->toBe('op2')
            ->and($labor->version)->toBe(1);
    });

    it('pasa a CONFIRMADA sin insumos', function () {
        $labor = laborProgramada();
        $labor->realizar('op2', 'h', utc('2026-11-20T10:00:00Z'), utc('2026-11-20T10:00:00Z'), 'Hecha', [],
            new Responsable('tec-1', 'Ana'), ValidacionCampania::VALIDADA, utc('2026-11-20T10:06:00Z'));

        expect($labor->estado)->toBe(EstadoLabor::CONFIRMADA)->and($labor->observaciones)->toBe('Hecha');
    });

    it('solo se realiza una labor PROGRAMADA', function () {
        $labor = laborRealizada();

        expect(codigoDe(fn () => $labor->realizar('op2', 'h', utc('2026-11-02T13:00:00Z'), utc('2026-11-02T13:00:00Z'), null, [],
            new Responsable('tec-1', 'Ana'), ValidacionCampania::VALIDADA, utc('2026-11-02T14:00:00Z'))))->toBe('LABOR_NO_PROGRAMADA');
    });

    it('una programada con la validación diferida todavía no se puede realizar', function () {
        expect(codigoDe(fn () => laborProgramada(ValidacionCampania::PENDIENTE)->exigirProgramada()))->toBe('LABOR_NO_PROGRAMADA');
    });
});

describe('validación diferida (RQ-LAB-10)', function () {
    it('válida: pasa al estado que le corresponde', function (Closure $crear, EstadoLabor $esperado) {
        $labor = $crear();
        $labor->aplicarValidacion(null, utc('2026-11-02T14:05:00Z'));

        expect($labor->estado)->toBe($esperado)
            ->and($labor->validacionPendiente())->toBeFalse()
            ->and($labor->fechaProximoValidacion)->toBeNull()
            ->and($labor->version)->toBe(1);
    })->with([
        'programada' => [fn () => laborProgramada(ValidacionCampania::PENDIENTE), EstadoLabor::PROGRAMADA],
        'realizada sin insumos' => [fn () => laborRealizada([], ValidacionCampania::PENDIENTE), EstadoLabor::CONFIRMADA],
        'realizada con insumos' => [fn () => laborRealizada([urea()], ValidacionCampania::PENDIENTE), EstadoLabor::PENDIENTE],
    ]);

    it('rechazada: queda RECHAZADA con el motivo', function () {
        $labor = laborRealizada([urea()], ValidacionCampania::PENDIENTE);
        $labor->aplicarValidacion((new CampaniaConsultada('c1', 'p1', 'FINALIZADA'))->rechazoPara('p1'), utc('2026-11-02T14:05:00Z'));

        expect($labor->estado)->toBe(EstadoLabor::RECHAZADA)
            ->and($labor->motivo?->codigo)->toBe('CAMPANIA_FINALIZADA');
    });

    it('pospone con espera de 2, 4, 8 y luego 15 minutos', function () {
        $labor = laborRealizada([], ValidacionCampania::PENDIENTE);
        $ahora = utc('2026-11-02T15:00:00Z');
        $esperas = [];
        foreach (range(1, 6) as $_) {
            $labor->posponerValidacion($ahora);
            $esperas[] = ($labor->fechaProximoValidacion->getTimestamp() - $ahora->getTimestamp()) / 60;
        }

        expect($esperas)->toBe([2, 4, 8, 15, 15, 15])
            ->and($labor->validacionPendiente())->toBeTrue();
    });
});

describe('campaña consultada (RN-06)', function () {
    it('rechaza una campaña finalizada o de otra parcela y acepta las demás', function () {
        expect((new CampaniaConsultada('c1', 'p1', 'FINALIZADA'))->rechazoPara('p1')?->codigo)->toBe('CAMPANIA_FINALIZADA')
            ->and((new CampaniaConsultada('c1', 'p1', 'EN_CURSO'))->rechazoPara('p2')?->codigo)->toBe('PARCELA_NO_CORRESPONDE')
            ->and((new CampaniaConsultada('c1', 'p1', 'PLANIFICADA'))->rechazoPara('p1'))->toBeNull()
            ->and((new CampaniaConsultada('c1', 'p1', 'EN_CURSO'))->rechazoPara('p1'))->toBeNull();
    });
});
