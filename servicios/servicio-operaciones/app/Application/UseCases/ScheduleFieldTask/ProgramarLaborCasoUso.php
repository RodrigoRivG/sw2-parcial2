<?php

namespace App\Application\UseCases\ScheduleFieldTask;

use App\Application\Security\SinPermiso;
use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\RegisterFieldTask\CreacionLabor;
use App\Application\UseCases\RegisterFieldTask\ResultadoLabor;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\Responsable;
use App\Domain\FieldTask\ValidacionCampania;
use App\Domain\Shared\Huella;
use DateTimeImmutable;

/**
 * Programa una labor futura (spec-labores.md Historia 2): sin efectos en inventario ni costos (RN-07).
 */
final class ProgramarLaborCasoUso
{
    public function __construct(private readonly CreacionLabor $creacion) {}

    public function ejecutar(ProgramarLaborEntrada $entrada, UsuarioAutenticado $usuario): ResultadoLabor
    {
        if (! $usuario->tieneRol('administrador', 'tecnico_campo')) {
            throw new SinPermiso;
        }

        $id = strtolower($entrada->idOperacion);
        $huella = Huella::calcular([
            'operacion' => 'PROGRAMAR_LABOR',
            'idOperacion' => $id,
            'fechaCreacion' => $entrada->fechaCreacion->format('Y-m-d\TH:i:s\Z'),
            'tipoLabor' => $entrada->tipoLabor->value,
            'idParcela' => strtolower($entrada->idParcela),
            'idCampania' => strtolower($entrada->idCampania),
            'fechaProgramada' => $entrada->fechaProgramada,
            'observaciones' => $entrada->observaciones,
        ], $usuario->id);

        return $this->creacion->crear(
            $id,
            $huella,
            strtolower($entrada->idCampania),
            strtolower($entrada->idParcela),
            'PROGRAMAR_LABOR',
            $usuario->id,
            fn (DateTimeImmutable $ahora) => LaborAgricola::validarProgramacion($entrada->fechaProgramada, $entrada->fechaCreacion, $ahora),
            fn (ValidacionCampania $validacion, DateTimeImmutable $ahora) => LaborAgricola::programar(
                $id,
                $huella,
                $entrada->tipoLabor,
                strtolower($entrada->idParcela),
                strtolower($entrada->idCampania),
                $entrada->fechaProgramada,
                $entrada->fechaCreacion,
                $entrada->observaciones,
                new Responsable($usuario->id, $usuario->nombre),
                $validacion,
                $ahora,
            ),
        );
    }
}
