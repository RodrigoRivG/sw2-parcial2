<?php

namespace App\InterfaceAdapters\Http\Controllers;

use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\QueryFieldTasks\ConsultarLaboresCasoUso;
use App\Application\UseCases\RegisterFieldTask\RealizarLaborCasoUso;
use App\Application\UseCases\RegisterFieldTask\RealizarLaborEntrada;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborCasoUso;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborEntrada;
use App\Application\UseCases\RegisterFieldTask\ResultadoLabor;
use App\Application\UseCases\ScheduleFieldTask\ProgramarLaborCasoUso;
use App\Application\UseCases\ScheduleFieldTask\ProgramarLaborEntrada;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\TipoLabor;
use App\InterfaceAdapters\Http\Requests\CrearLaborRequest;
use App\InterfaceAdapters\Http\Requests\ListarLaboresRequest;
use App\InterfaceAdapters\Http\Requests\RealizarLaborRequest;
use App\InterfaceAdapters\Http\Requests\SolicitudEstricta;
use App\InterfaceAdapters\Http\Resources\LaborRecurso;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

final class LaborControlador
{
    public function crear(CrearLaborRequest $request, ProgramarLaborCasoUso $programar, RegistrarLaborCasoUso $registrar): JsonResponse
    {
        $usuario = self::usuario($request);
        $comun = [
            'idOperacion' => (string) $request->input('idOperacion'),
            'fechaCreacion' => SolicitudEstricta::fechaHora((string) $request->input('fechaCreacion')),
            'tipoLabor' => TipoLabor::from((string) $request->input('tipoLabor')),
            'idParcela' => (string) $request->input('idParcela'),
            'idCampania' => (string) $request->input('idCampania'),
        ];

        $resultado = $request->esProgramacion()
            ? $programar->ejecutar(new ProgramarLaborEntrada(
                ...$comun,
                fechaProgramada: (string) $request->input('fechaProgramada'),
                observaciones: $request->input('observaciones'),
            ), $usuario)
            : $registrar->ejecutar(new RegistrarLaborEntrada(
                ...$comun,
                fechaEjecucion: SolicitudEstricta::fechaHora((string) $request->input('fechaEjecucion')),
                observaciones: $request->input('observaciones'),
                insumos: $request->input('insumos', []),
            ), $usuario);

        return self::respuestaCreacion($resultado);
    }

    public function realizar(RealizarLaborRequest $request, string $id, RealizarLaborCasoUso $realizar): JsonResponse
    {
        $resultado = $realizar->ejecutar(new RealizarLaborEntrada(
            idLabor: $id,
            idOperacion: (string) $request->input('idOperacion'),
            fechaCreacion: SolicitudEstricta::fechaHora((string) $request->input('fechaCreacion')),
            fechaEjecucion: SolicitudEstricta::fechaHora((string) $request->input('fechaEjecucion')),
            observaciones: $request->input('observaciones'),
            insumos: $request->input('insumos', []),
        ), self::usuario($request));

        return new JsonResponse(LaborRecurso::aArreglo($resultado->labor));
    }

    public function listar(ListarLaboresRequest $request, ConsultarLaboresCasoUso $consultar): JsonResponse
    {
        $pagina = $consultar->listar($request->filtro(), $request->mias(), self::usuario($request));

        return new JsonResponse([
            'items' => array_map(fn (LaborAgricola $labor) => LaborRecurso::aArreglo($labor), $pagina->items),
            'siguienteCursor' => $pagina->siguienteCursor,
        ]);
    }

    public function detalle(Request $request, string $id, ConsultarLaboresCasoUso $consultar): JsonResponse
    {
        return new JsonResponse(LaborRecurso::aArreglo($consultar->detalle($id, self::usuario($request))));
    }

    private static function respuestaCreacion(ResultadoLabor $resultado): JsonResponse
    {
        if ($resultado->repetida) {
            return new JsonResponse(LaborRecurso::aArreglo($resultado->labor));
        }

        return new JsonResponse(LaborRecurso::aArreglo($resultado->labor), 201, [
            'Location' => url("/api/operaciones/v1/labores/{$resultado->labor->id}"),
        ]);
    }

    private static function usuario(Request $request): UsuarioAutenticado
    {
        return $request->attributes->get(UsuarioAutenticado::class);
    }
}
