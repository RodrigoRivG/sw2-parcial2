<?php

namespace App\Application\UseCases\RegisterFieldTask;

use App\Application\Contracts\ConflictoEscritura;
use App\Application\Contracts\RegistroAuditoria;
use App\Application\Contracts\Reloj;
use App\Application\Contracts\UnidadTrabajo;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\RepositorioLabor;
use App\Domain\FieldTask\ValidacionCampania;
use App\Domain\Shared\ExcepcionDominio;
use DateTimeImmutable;

/**
 * Flujo común de programar y registrar una labor (spec-labores.md 2.4): idempotencia, reglas, campaña y guardado.
 */
final class CreacionLabor
{
    public function __construct(
        private readonly RepositorioLabor $repositorio,
        private readonly UnidadTrabajo $unidadTrabajo,
        private readonly RegistroAuditoria $auditoria,
        private readonly VerificadorCampania $verificador,
        private readonly Reloj $reloj,
    ) {}

    /**
     * @param  callable(DateTimeImmutable): void  $validarReglas  reglas del dominio, antes de consultar la campaña
     * @param  callable(ValidacionCampania, DateTimeImmutable): LaborAgricola  $fabricar
     */
    public function crear(
        string $id,
        string $huella,
        string $idCampania,
        string $idParcela,
        string $accion,
        string $actor,
        callable $validarReglas,
        callable $fabricar,
    ): ResultadoLabor {
        $existente = $this->repositorio->buscar($id);
        if ($existente !== null) {
            return $this->repeticion($existente, $huella);
        }

        $ahora = $this->reloj->ahora();
        $validarReglas($ahora);
        $validacion = $this->verificador->exigir($idCampania, $idParcela);
        $labor = $fabricar($validacion, $ahora);

        try {
            $this->unidadTrabajo->ejecutar(function () use ($labor, $accion, $actor) {
                $this->repositorio->guardarNueva($labor);
                $this->auditoria->registrar($actor, $accion, 'LABOR', $labor->id);
            });
        } catch (ConflictoEscritura) {
            // Otra solicitud con el mismo idOperacion ganó la carrera
            $ganadora = $this->repositorio->buscar($id) ?? throw new \LogicException('La labor que ganó la carrera no existe.');

            return $this->repeticion($ganadora, $huella);
        }

        return new ResultadoLabor($labor, false);
    }

    private function repeticion(LaborAgricola $existente, string $huella): ResultadoLabor
    {
        if (! hash_equals($existente->huellaCreacion, $huella)) {
            throw self::conflictoIdempotencia();
        }

        return new ResultadoLabor($existente, true);
    }

    public static function conflictoIdempotencia(): ExcepcionDominio
    {
        return ExcepcionDominio::conflicto('CONFLICTO_IDEMPOTENCIA', 'La operación ya se procesó con otro contenido.');
    }
}
