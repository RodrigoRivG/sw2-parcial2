<?php

require_once __DIR__.'/Dobles.php';

use App\Application\Contracts\AlmacenamientoArchivos;
use App\Application\Contracts\ConflictoEscritura;
use App\Application\Contracts\UrlTemporal;
use App\Application\Security\SinPermiso;
use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\RegisterIncident\NotificacionIncidencia;
use App\Application\UseCases\RegisterIncident\RegistrarIncidenciaCasoUso;
use App\Application\UseCases\RegisterIncident\RegistrarIncidenciaEntrada;
use App\Application\UseCases\RegisterIncident\RepublicarEventosIncidenciasCasoUso;
use App\Domain\Incident\Incidencia;
use App\Domain\Incident\RepositorioIncidencia;
use App\Domain\Incident\TipoIncidencia;
use App\Domain\Shared\ExcepcionDominio;
use Psr\Log\NullLogger;
use Tests\Support\RelojFijo;
use Tests\Unit\Application\AuditoriaEnMemoria;
use Tests\Unit\Application\PublicadorEnMemoria;
use Tests\Unit\Application\UnidadTrabajoDirecta;

final class AlmacenamientoEnMemoria implements AlmacenamientoArchivos
{
    /** @var array<string, string> */
    public array $objetos = [];

    public function guardar(string $clave, string $contenido, string $tipoContenido): void
    {
        $this->objetos[$clave] = $contenido;
    }

    public function borrar(string $clave): void
    {
        unset($this->objetos[$clave]);
    }

    public function urlTemporal(string $clave, int $minutos): UrlTemporal
    {
        return new UrlTemporal("memoria://{$clave}", new DateTimeImmutable("+{$minutos} minutes"));
    }
}

final class RepositorioIncidenciaEnMemoria implements RepositorioIncidencia
{
    /** @var array<string, Incidencia> */
    public array $incidencias = [];

    /** @var array<string, bool> */
    public array $notificadas = [];

    public ?Incidencia $ganadoraCarrera = null;

    public bool $falla = false;

    public function buscar(string $id): ?Incidencia
    {
        return $this->incidencias[$id] ?? null;
    }

    public function guardarNueva(Incidencia $incidencia): void
    {
        if ($this->falla) {
            throw new RuntimeException('DynamoDB no responde');
        }
        if ($this->ganadoraCarrera !== null) {
            $this->incidencias[$this->ganadoraCarrera->id] = $this->ganadoraCarrera;
            throw new ConflictoEscritura('incidencia');
        }
        $this->incidencias[$incidencia->id] = $incidencia;
    }

    public function marcarNotificada(string $id): void
    {
        $this->notificadas[$id] = true;
    }

    public function pendientesDeNotificar(DateTimeImmutable $antesDe, int $maximo): array
    {
        return array_values(array_filter($this->incidencias, fn (Incidencia $i) => ! isset($this->notificadas[$i->id]) && $i->fechaRecepcion <= $antesDe));
    }
}

beforeEach(function () {
    $this->repositorio = new RepositorioIncidenciaEnMemoria;
    $this->almacenamiento = new AlmacenamientoEnMemoria;
    $this->publicador = new PublicadorEnMemoria;
    $this->auditoria = new AuditoriaEnMemoria;
    $this->reloj = new RelojFijo('2026-11-02T14:00:00Z');
    $this->notificacion = new NotificacionIncidencia($this->publicador, $this->repositorio, new NullLogger);
    $this->registrar = new RegistrarIncidenciaCasoUso($this->repositorio, $this->almacenamiento, new UnidadTrabajoDirecta, $this->auditoria,
        $this->notificacion, $this->reloj, new NullLogger);
    $this->tecnico = new UsuarioAutenticado('tec', 'Ana', ['tecnico_campo']);
});

function entradaIncidencia(string $foto = "\xFF\xD8\xFFuno", string $descripcion = 'Pulgón'): RegistrarIncidenciaEntrada
{
    $utc = new DateTimeZone('UTC');
    $fecha = new DateTimeImmutable('2026-11-02T13:50:00Z', $utc);

    return new RegistrarIncidenciaEntrada('I1', $fecha, TipoIncidencia::PLAGA, $descripcion, $fecha, 'P1', null, null, $foto, 'corr-1');
}

it('guarda la foto, la incidencia y su auditoría, publica el evento y marca la notificación', function () {
    $resultado = $this->registrar->ejecutar(entradaIncidencia(), $this->tecnico);

    expect($resultado->repetida)->toBeFalse()
        ->and($resultado->incidencia->id)->toBe('i1')
        ->and(array_keys($this->almacenamiento->objetos))->toBe([$resultado->incidencia->foto->clave])
        ->and($this->auditoria->registros[0]['accion'])->toBe('REGISTRAR_INCIDENCIA')
        ->and($this->publicador->eventos[0])->toMatchArray(['routingKey' => 'operaciones.incidencia.registrada', 'tipo' => 'IncidenciaRegistrada', 'idCorrelacion' => 'corr-1'])
        ->and($this->repositorio->notificadas)->toBe(['i1' => true]);
});

it('una repetición no sube otra foto ni publica; con otra foto es conflicto', function () {
    $this->registrar->ejecutar(entradaIncidencia(), $this->tecnico);

    expect($this->registrar->ejecutar(entradaIncidencia(), $this->tecnico)->repetida)->toBeTrue()
        ->and($this->publicador->eventos)->toHaveCount(1)
        ->and(fn () => $this->registrar->ejecutar(entradaIncidencia("\xFF\xD8\xFFdos"), $this->tecnico))
        ->toThrow(fn (ExcepcionDominio $e) => expect($e->codigo)->toBe('CONFLICTO_IDEMPOTENCIA'))
        ->and($this->almacenamiento->objetos)->toHaveCount(1);
});

it('si otra solicitud gana la carrera con otra foto, borra la foto subida y responde conflicto', function () {
    $otro = new RegistrarIncidenciaCasoUso(new RepositorioIncidenciaEnMemoria, new AlmacenamientoEnMemoria, new UnidadTrabajoDirecta,
        new AuditoriaEnMemoria, $this->notificacion, $this->reloj, new NullLogger);
    $this->repositorio->ganadoraCarrera = $otro->ejecutar(entradaIncidencia("\xFF\xD8\xFFganadora"), $this->tecnico)->incidencia;

    expect(fn () => $this->registrar->ejecutar(entradaIncidencia("\xFF\xD8\xFFperdedora"), $this->tecnico))
        ->toThrow(fn (ExcepcionDominio $e) => expect($e->codigo)->toBe('CONFLICTO_IDEMPOTENCIA'))
        ->and($this->almacenamiento->objetos)->toBe([]);
});

it('si DynamoDB falla, borra la foto subida y no publica', function () {
    $this->repositorio->falla = true;

    expect(fn () => $this->registrar->ejecutar(entradaIncidencia(), $this->tecnico))->toThrow(RuntimeException::class, 'DynamoDB');
    expect($this->almacenamiento->objetos)->toBe([])->and($this->publicador->eventos)->toBe([]);
});

it('si el broker falla, la incidencia queda registrada y pendiente; la tarea la republica pasado 1 minuto', function () {
    $this->publicador->falla = true;
    $this->registrar->ejecutar(entradaIncidencia(), $this->tecnico);
    expect($this->repositorio->notificadas)->toBe([]);

    $this->publicador->falla = false;
    $republicar = new RepublicarEventosIncidenciasCasoUso($this->repositorio, $this->notificacion, $this->reloj);
    expect($republicar->ejecutar())->toBe(0);

    $this->reloj->avanzar('+61 seconds');
    expect($republicar->ejecutar())->toBe(1)
        ->and($republicar->ejecutar())->toBe(0)
        ->and($this->publicador->eventos[0]['datos']['idIncidencia'])->toBe('i1');
});

it('valida la foto antes de subir nada y exige tecnico_campo', function () {
    expect(fn () => $this->registrar->ejecutar(entradaIncidencia('GIF89a'), $this->tecnico))->toThrow(ExcepcionDominio::class)
        ->and(fn () => $this->registrar->ejecutar(entradaIncidencia(), new UsuarioAutenticado('g', 'G', ['gerencia'])))->toThrow(SinPermiso::class)
        ->and($this->almacenamiento->objetos)->toBe([]);
});
