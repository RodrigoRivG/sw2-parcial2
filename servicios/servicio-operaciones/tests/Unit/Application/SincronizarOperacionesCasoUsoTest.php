<?php

require_once __DIR__.'/Dobles.php';

use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\RegisterFieldTask\CreacionLabor;
use App\Application\UseCases\RegisterFieldTask\RealizarLaborCasoUso;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborCasoUso;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborEntrada;
use App\Application\UseCases\RegisterFieldTask\VerificadorCampania;
use App\Application\UseCases\RegisterIncident\NotificacionIncidencia;
use App\Application\UseCases\RegisterIncident\RegistrarIncidenciaCasoUso;
use App\Application\UseCases\ScheduleFieldTask\ProgramarLaborCasoUso;
use App\Application\UseCases\SyncOfflineOperations\OperacionSincronizacion;
use App\Application\UseCases\SyncOfflineOperations\PasarelaCampaniaConCache;
use App\Application\UseCases\SyncOfflineOperations\ResultadoOperacion;
use App\Application\UseCases\SyncOfflineOperations\SincronizarOperacionesCasoUso;
use App\Domain\FieldTask\CampaniaConsultada;
use App\Domain\FieldTask\TipoLabor;
use App\Domain\Shared\Motivo;
use App\Domain\Shared\ResultadoSincronizacion;
use Psr\Log\NullLogger;
use Tests\Support\RelojFijo;
use Tests\Unit\Application\AlmacenamientoEnMemoria;
use Tests\Unit\Application\AuditoriaEnMemoria;
use Tests\Unit\Application\PasarelaCampaniaFalsa;
use Tests\Unit\Application\PublicadorEnMemoria;
use Tests\Unit\Application\RepositorioIncidenciaEnMemoria;
use Tests\Unit\Application\RepositorioLaborEnMemoria;
use Tests\Unit\Application\UnidadTrabajoDirecta;

use function Tests\Unit\Application\iniciarSagaEnMemoria;

beforeEach(function () {
    $this->reloj = new RelojFijo('2026-11-02T14:00:00Z');
    $this->labores = new RepositorioLaborEnMemoria;
    $this->gestion = new PasarelaCampaniaFalsa;
    $this->gestion->campanias['c1'] = new CampaniaConsultada('c1', 'p1', 'EN_CURSO');
    $this->gestion->campanias['c2'] = new CampaniaConsultada('c2', 'p1', 'FINALIZADA');
    $this->cache = new PasarelaCampaniaConCache($this->gestion);
    $auditoria = new AuditoriaEnMemoria;
    $verificador = new VerificadorCampania($this->cache, new NullLogger);
    $creacion = new CreacionLabor($this->labores, new UnidadTrabajoDirecta, $auditoria, $verificador, $this->reloj, iniciarSagaEnMemoria($auditoria));
    $incidencias = new RepositorioIncidenciaEnMemoria;
    $this->sincronizar = new SincronizarOperacionesCasoUso(
        new ProgramarLaborCasoUso($creacion),
        new RegistrarLaborCasoUso($creacion),
        new RealizarLaborCasoUso($this->labores, new UnidadTrabajoDirecta, $auditoria, $verificador, $this->reloj, iniciarSagaEnMemoria($auditoria)),
        new RegistrarIncidenciaCasoUso($incidencias, new AlmacenamientoEnMemoria, new UnidadTrabajoDirecta, $auditoria,
            new NotificacionIncidencia(new PublicadorEnMemoria, $incidencias, new NullLogger), $this->reloj, new NullLogger),
        $this->cache,
        new NullLogger,
    );
    $this->tecnico = new UsuarioAutenticado('tec', 'Ana', ['tecnico_campo']);
});

function operacion(int $indice, string $id, string $creacion, string $campania = 'c1'): OperacionSincronizacion
{
    $fecha = new DateTimeImmutable($creacion, new DateTimeZone('UTC'));

    return new OperacionSincronizacion($indice, 'REGISTRAR_LABOR', $id, $fecha,
        new RegistrarLaborEntrada($id, $fecha, TipoLabor::RIEGO, 'p1', $campania, $fecha, null, []));
}

/** @param list<ResultadoOperacion> $resultados */
function resumen(array $resultados): array
{
    return array_map(fn (ResultadoOperacion $r) => $r->idOperacion.':'.($r->resultado === ResultadoSincronizacion::SINCRONIZADA ? $r->estado : $r->codigo), $resultados);
}

it('procesa por fecha de creación y, a igual fecha, por idOperacion; los sobres inválidos van al final', function () {
    $sinSobre = new OperacionSincronizacion(9, null, null, null, null, new Motivo('DATOS_INVALIDOS', 'Sin sobre.'));

    $resultados = $this->sincronizar->ejecutar([
        operacion(0, 'op-c', '2026-11-02T10:02:00Z'),
        $sinSobre,
        operacion(1, 'op-b', '2026-11-02T09:15:00Z'),
        operacion(2, 'op-a', '2026-11-02T09:15:00Z'),
    ], $this->tecnico, 'corr');

    expect(resumen($resultados))->toBe(['op-a:CONFIRMADA', 'op-b:CONFIRMADA', 'op-c:CONFIRMADA', ':DATOS_INVALIDOS']);
});

it('un error de negocio no aborta el lote y no es reintentable', function () {
    $resultados = $this->sincronizar->ejecutar([
        operacion(0, 'op-1', '2026-11-02T09:00:00Z'),
        operacion(1, 'op-2', '2026-11-02T09:01:00Z', campania: 'c2'),
        operacion(2, 'op-3', '2026-11-02T09:02:00Z'),
    ], $this->tecnico, 'corr');

    expect(resumen($resultados))->toBe(['op-1:CONFIRMADA', 'op-2:CAMPANIA_FINALIZADA', 'op-3:CONFIRMADA'])
        ->and($resultados[1]->reintentable)->toBeFalse();
});

it('un fallo técnico es ERROR_INTERNO reintentable, sin detalles internos, y el lote sigue', function () {
    $this->labores->fallanAlGuardar = ['op-2'];

    $resultados = $this->sincronizar->ejecutar([
        operacion(0, 'op-1', '2026-11-02T09:00:00Z'),
        operacion(1, 'op-2', '2026-11-02T09:01:00Z'),
        operacion(2, 'op-3', '2026-11-02T09:02:00Z'),
    ], $this->tecnico, 'corr');

    expect(resumen($resultados))->toBe(['op-1:CONFIRMADA', 'op-2:ERROR_INTERNO', 'op-3:CONFIRMADA'])
        ->and($resultados[1]->reintentable)->toBeTrue()
        ->and($resultados[1]->mensaje)->not->toContain('DynamoDB');
});

it('una repetición se informa como SINCRONIZADA repetida', function () {
    $this->sincronizar->ejecutar([operacion(0, 'op-1', '2026-11-02T09:00:00Z')], $this->tecnico, 'corr');

    $resultados = $this->sincronizar->ejecutar([operacion(0, 'op-1', '2026-11-02T09:00:00Z')], $this->tecnico, 'corr');

    expect($resultados[0]->repetida)->toBeTrue()->and($resultados[0]->idRecurso)->toBe('op-1');
});

it('consulta cada campaña una sola vez por lote, también si gestión no responde, y deja de cachear al terminar', function () {
    $this->sincronizar->ejecutar([
        operacion(0, 'op-1', '2026-11-02T09:00:00Z'),
        operacion(1, 'op-2', '2026-11-02T09:01:00Z'),
        operacion(2, 'op-3', '2026-11-02T09:02:00Z', campania: 'c2'),
    ], $this->tecnico, 'corr');
    expect($this->gestion->consultas)->toBe(2);

    $this->gestion->disponible = false;
    $this->gestion->consultas = 0;
    $resultados = $this->sincronizar->ejecutar([
        operacion(0, 'op-4', '2026-11-02T09:00:00Z'),
        operacion(1, 'op-5', '2026-11-02T09:01:00Z'),
    ], $this->tecnico, 'corr');
    expect($this->gestion->consultas)->toBe(1)
        ->and(resumen($resultados))->toBe(['op-4:PENDIENTE', 'op-5:PENDIENTE']);

    // Fuera de un lote, cada consulta va a gestión
    $this->gestion->disponible = true;
    $this->cache->consultar('c1');
    $this->cache->consultar('c1');
    expect($this->gestion->consultas)->toBe(3);
});
