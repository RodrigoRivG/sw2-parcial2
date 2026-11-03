<?php

namespace Tests\Unit\Application;

use App\Application\Contracts\AlmacenamientoArchivos;
use App\Application\Contracts\CampaniaNoDisponible;
use App\Application\Contracts\ConflictoEscritura;
use App\Application\Contracts\PasarelaCampania;
use App\Application\Contracts\PublicacionFallida;
use App\Application\Contracts\PublicadorMensajes;
use App\Application\Contracts\RegistroAuditoria;
use App\Application\Contracts\UnidadTrabajo;
use App\Application\Contracts\UrlTemporal;
use App\Application\UseCases\Saga\EnvioComandos;
use App\Application\UseCases\Saga\IniciarSaga;
use App\Domain\FieldTask\CampaniaConsultada;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\RepositorioLabor;
use App\Domain\Incident\Incidencia;
use App\Domain\Incident\RepositorioIncidencia;
use App\Domain\Saga\ConfiguracionSaga;
use App\Domain\Saga\Participante;
use App\Domain\Saga\RepositorioSaga;
use App\Domain\Saga\Saga;
use DateTimeImmutable;
use Psr\Log\NullLogger;

/**
 * Dobles escritos a mano para los tests unitarios de Application (sin Laravel ni DynamoDB).
 */
final class RepositorioLaborEnMemoria implements RepositorioLabor
{
    /** @var array<string, LaborAgricola> */
    public array $labores = [];

    /** Simula otra solicitud que gana la carrera justo antes de guardar. */
    public ?LaborAgricola $ganadoraCarrera = null;

    /** Ids cuya escritura falla como si DynamoDB no respondiera. */
    public array $fallanAlGuardar = [];

    public function buscar(string $id): ?LaborAgricola
    {
        return isset($this->labores[$id]) ? clone $this->labores[$id] : null;
    }

    public function guardarNueva(LaborAgricola $labor): void
    {
        if (in_array($labor->id, $this->fallanAlGuardar, true)) {
            throw new \RuntimeException('DynamoDB no responde');
        }
        if ($this->ganadoraCarrera !== null) {
            $this->labores[$this->ganadoraCarrera->id] = $this->ganadoraCarrera;
            $this->ganadoraCarrera = null;
        }
        if (isset($this->labores[$labor->id])) {
            throw new ConflictoEscritura('labor');
        }
        $this->labores[$labor->id] = clone $labor;
    }

    public function actualizar(LaborAgricola $labor, int $versionLeida, ?EstadoLabor $estadoEsperado = null): void
    {
        if ($this->ganadoraCarrera !== null) {
            $this->labores[$this->ganadoraCarrera->id] = $this->ganadoraCarrera;
            $this->ganadoraCarrera = null;
        }
        $actual = $this->labores[$labor->id] ?? null;
        if ($actual === null || $actual->version !== $versionLeida || ($estadoEsperado !== null && $actual->estado !== $estadoEsperado)) {
            throw new ConflictoEscritura('labor');
        }
        $this->labores[$labor->id] = clone $labor;
    }

    public function conValidacionVencida(DateTimeImmutable $ahora, int $maximo): array
    {
        $vencidas = array_filter(
            $this->labores,
            fn (LaborAgricola $l) => $l->validacionPendiente() && $l->fechaProximoValidacion <= $ahora,
        );

        return array_map(fn (LaborAgricola $l) => clone $l, array_values(array_slice($vencidas, 0, $maximo)));
    }

    public function pendientesSinSaga(int $maximo): array
    {
        return array_map(fn (LaborAgricola $l) => clone $l, array_values(array_filter($this->labores, fn (LaborAgricola $l) => $l->requiereSaga())));
    }
}

final class RepositorioSagaEnMemoria implements RepositorioSaga
{
    /** @var array<string, Saga> */
    public array $sagas = [];

    /** Simula otra escritura (otra respuesta o la recuperación) justo antes de guardar. */
    public ?\Closure $antesDeActualizar = null;

    public function buscar(string $idSaga): ?Saga
    {
        return isset($this->sagas[$idSaga]) ? clone $this->sagas[$idSaga] : null;
    }

    public function guardarNueva(Saga $saga): void
    {
        if (isset($this->sagas[$saga->idSaga])) {
            throw new ConflictoEscritura('saga');
        }
        $this->sagas[$saga->idSaga] = clone $saga;
    }

    public function actualizar(Saga $saga, int $versionLeida): void
    {
        if ($this->antesDeActualizar !== null) {
            $antes = $this->antesDeActualizar;
            $this->antesDeActualizar = null;
            $antes($this);
        }
        if (($this->sagas[$saga->idSaga] ?? null)?->version !== $versionLeida) {
            throw new ConflictoEscritura('saga');
        }
        $this->sagas[$saga->idSaga] = clone $saga;
    }

    public function vencidas(DateTimeImmutable $ahora, int $maximo): array
    {
        return array_values(array_map(
            fn (Saga $s) => $s->idSaga,
            array_filter($this->sagas, fn (Saga $s) => $s->estaVencida($ahora)),
        ));
    }
}

final class PublicadorEnMemoria implements PublicadorMensajes
{
    /** @var list<array{destino: Participante, tipo: string, datos: array<string, mixed>, idCorrelacion: string}> */
    public array $enviados = [];

    public bool $falla = false;

    public function enviarComando(Participante $destino, string $tipo, array $datos, string $idCorrelacion): string
    {
        if ($this->falla) {
            throw new PublicacionFallida('broker caído');
        }
        $this->enviados[] = ['destino' => $destino, 'tipo' => $tipo, 'datos' => $datos, 'idCorrelacion' => $idCorrelacion];

        return 'msg-'.count($this->enviados);
    }

    /** @var list<array{routingKey: string, tipo: string, datos: array<string, mixed>, idCorrelacion: string}> */
    public array $eventos = [];

    public function publicarEvento(string $routingKey, string $tipo, array $datos, string $idCorrelacion): string
    {
        if ($this->falla) {
            throw new PublicacionFallida('broker caído');
        }
        $this->eventos[] = ['routingKey' => $routingKey, 'tipo' => $tipo, 'datos' => $datos, 'idCorrelacion' => $idCorrelacion];

        return 'evt-'.count($this->eventos);
    }
}

function iniciarSagaEnMemoria(AuditoriaEnMemoria $auditoria, ?RepositorioSagaEnMemoria $sagas = null, ?PublicadorEnMemoria $publicador = null): IniciarSaga
{
    return new IniciarSaga($sagas ?? new RepositorioSagaEnMemoria, $auditoria,
        new EnvioComandos($publicador ?? new PublicadorEnMemoria, new NullLogger), new ConfiguracionSaga);
}

final class UnidadTrabajoDirecta implements UnidadTrabajo
{
    public int $confirmadas = 0;

    public function ejecutar(callable $operacion): mixed
    {
        $resultado = $operacion();
        $this->confirmadas++;

        return $resultado;
    }
}

final class AuditoriaEnMemoria implements RegistroAuditoria
{
    /** @var list<array{actor: string, accion: string, entidad: string, idEntidad: string}> */
    public array $registros = [];

    public function registrar(string $actor, string $accion, string $entidad, string $idEntidad): void
    {
        $this->registros[] = ['actor' => $actor, 'accion' => $accion, 'entidad' => $entidad, 'idEntidad' => $idEntidad];
    }
}

final class PasarelaCampaniaFalsa implements PasarelaCampania
{
    /** @var array<string, CampaniaConsultada> */
    public array $campanias = [];

    public bool $disponible = true;

    public int $consultas = 0;

    public function consultar(string $idCampania): ?CampaniaConsultada
    {
        $this->consultas++;
        if (! $this->disponible) {
            throw new CampaniaNoDisponible('sin respuesta');
        }

        return $this->campanias[$idCampania] ?? null;
    }
}

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
            throw new \RuntimeException('DynamoDB no responde');
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
