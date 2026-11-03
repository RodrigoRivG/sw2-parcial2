<?php

namespace App\InterfaceAdapters\Http\Controllers;

use App\Application\UseCases\Saga\ConsultarSagaCasoUso;
use App\InterfaceAdapters\Http\Resources\SagaRecurso;
use Illuminate\Http\JsonResponse;

final class SagaControlador
{
    public function detalle(string $id, ConsultarSagaCasoUso $consultar): JsonResponse
    {
        return new JsonResponse(SagaRecurso::aArreglo($consultar->ejecutar($id)));
    }
}
