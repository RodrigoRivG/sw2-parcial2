<?php

namespace Tests\Unit\Application;

use App\Application\Contracts\CampaniaNoDisponible;
use App\Application\Contracts\ConflictoEscritura;
use App\Application\Contracts\PasarelaCampania;
use App\Application\Contracts\RegistroAuditoria;
use App\Application\Contracts\UnidadTrabajo;
use App\Domain\FieldTask\CampaniaConsultada;
use App\Domain\FieldTask\EstadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\RepositorioLabor;
use DateTimeImmutable;

/**
 * Dobles escritos a mano para los tests unitarios de Application (sin Laravel ni DynamoDB).
 */
final class RepositorioLaborEnMemoria implements RepositorioLabor
{
    /** @var array<string, LaborAgricola> */
    public array $labores = [];

    /** Simula otra solicitud que gana la carrera justo antes de guardar. */
    public ?LaborAgricola $ganadoraCarrera = null;

    public function buscar(string $id): ?LaborAgricola
    {
        return isset($this->labores[$id]) ? clone $this->labores[$id] : null;
    }

    public function guardarNueva(LaborAgricola $labor): void
    {
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
