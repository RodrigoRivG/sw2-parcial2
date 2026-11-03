<?php

namespace App\Application\UseCases\RegisterFieldTask;

use App\Application\Security\SinPermiso;
use App\Application\Security\UsuarioAutenticado;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\Responsable;
use App\Domain\FieldTask\ValidacionCampania;
use App\Domain\Shared\Huella;
use DateTimeImmutable;

/**
 * Registra una labor ya realizada (spec-labores.md Historia 1): sin insumos se confirma; con insumos queda PENDIENTE.
 */
final class RegistrarLaborCasoUso
{
    public function __construct(private readonly CreacionLabor $creacion) {}

    public function ejecutar(RegistrarLaborEntrada $entrada, UsuarioAutenticado $usuario): ResultadoLabor
    {
        if (! $usuario->tieneRol('tecnico_campo')) {
            throw new SinPermiso('Solo un técnico de campo puede registrar labores realizadas.');
        }

        $id = strtolower($entrada->idOperacion);
        $consumos = InsumosEntrada::aConsumos($entrada->insumos);
        $huella = Huella::calcular([
            'operacion' => 'REGISTRAR_LABOR',
            'idOperacion' => $id,
            'fechaCreacion' => $entrada->fechaCreacion->format('Y-m-d\TH:i:s\Z'),
            'tipoLabor' => $entrada->tipoLabor->value,
            'idParcela' => strtolower($entrada->idParcela),
            'idCampania' => strtolower($entrada->idCampania),
            'fechaEjecucion' => $entrada->fechaEjecucion->format('Y-m-d\TH:i:s\Z'),
            'observaciones' => $entrada->observaciones,
            'insumos' => InsumosEntrada::paraHuella($consumos),
        ], $usuario->id);

        return $this->creacion->crear(
            $id,
            $huella,
            strtolower($entrada->idCampania),
            strtolower($entrada->idParcela),
            'REGISTRAR_LABOR',
            $usuario->id,
            fn (DateTimeImmutable $ahora) => LaborAgricola::validarEjecucion($entrada->fechaEjecucion, $entrada->fechaCreacion, $ahora),
            fn (ValidacionCampania $validacion, DateTimeImmutable $ahora) => LaborAgricola::registrarRealizada(
                $id,
                $huella,
                $entrada->tipoLabor,
                strtolower($entrada->idParcela),
                strtolower($entrada->idCampania),
                $entrada->fechaEjecucion,
                $entrada->fechaCreacion,
                $entrada->observaciones,
                $consumos,
                new Responsable($usuario->id, $usuario->nombre),
                $validacion,
                $ahora,
            ),
        );
    }
}
