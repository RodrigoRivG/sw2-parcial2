<?php

namespace App\InterfaceAdapters\Http\Controllers;

use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\QueryFieldTasks\ConsultarLaboresCasoUso;
use App\Application\UseCases\RegisterFieldTask\RealizarLaborCasoUso;
use App\Application\UseCases\RegisterFieldTask\RealizarLaborEntrada;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborCasoUso;
use App\Application\UseCases\RegisterFieldTask\RegistrarLaborEntrada;
use App\Application\UseCases\RegisterFieldTask\ResultadoLabor;
use App\Application\UseCases\ResolveReview\ResolverRevisionCasoUso;
use App\Application\UseCases\ResolveReview\ResolverRevisionEntrada;
use App\Application\UseCases\ScheduleFieldTask\ProgramarLaborCasoUso;
use App\Application\UseCases\ScheduleFieldTask\ProgramarLaborEntrada;
use App\Domain\FieldTask\DecisionRevision;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\FieldTask\TipoLabor;
use App\InterfaceAdapters\Http\Requests\CrearLaborRequest;
use App\InterfaceAdapters\Http\Requests\ListarLaboresRequest;
use App\InterfaceAdapters\Http\Requests\RealizarLaborRequest;
use App\InterfaceAdapters\Http\Requests\ResolverRevisionRequest;
use App\InterfaceAdapters\Http\Requests\SolicitudEstricta;
use App\InterfaceAdapters\Http\Resources\LaborRecurso;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

final class LaborControlador
{
    public function crear(CrearLaborRequest $request, ProgramarLaborCasoUso $programar, RegistrarLaborCasoUso $registrar): JsonResponse
    {
        $entrada = self::entradaCreacion($request->all());
        $resultado = $entrada instanceof ProgramarLaborEntrada
            ? $programar->ejecutar($entrada, self::usuario($request))
            : $registrar->ejecutar($entrada, self::usuario($request));

        return self::respuestaCreacion($resultado);
    }

    public function realizar(RealizarLaborRequest $request, string $id, RealizarLaborCasoUso $realizar): JsonResponse
    {
        $resultado = $realizar->ejecutar(self::entradaRealizacion($id, $request->all()), self::usuario($request));

        return new JsonResponse(LaborRecurso::aArreglo($resultado->labor));
    }

    /**
     * Cuerpo ya validado de POST /labores → entrada del caso de uso. La usa también la sincronización.
     *
     * @param  array<string, mixed>  $datos
     */
    public static function entradaCreacion(array $datos): ProgramarLaborEntrada|RegistrarLaborEntrada
    {
        $comun = [
            'idOperacion' => (string) $datos['idOperacion'],
            'fechaCreacion' => SolicitudEstricta::fechaHora((string) $datos['fechaCreacion']),
            'tipoLabor' => TipoLabor::from((string) $datos['tipoLabor']),
            'idParcela' => (string) $datos['idParcela'],
            'idCampania' => (string) $datos['idCampania'],
        ];

        return isset($datos['fechaProgramada'])
            ? new ProgramarLaborEntrada(...$comun, fechaProgramada: (string) $datos['fechaProgramada'], observaciones: self::texto($datos['observaciones'] ?? null))
            : new RegistrarLaborEntrada(
                ...$comun,
                fechaEjecucion: SolicitudEstricta::fechaHora((string) $datos['fechaEjecucion']),
                observaciones: self::texto($datos['observaciones'] ?? null),
                insumos: $datos['insumos'] ?? [],
            );
    }

    /**
     * Cuerpo ya validado de la realización → entrada del caso de uso. La usa también la sincronización.
     *
     * @param  array<string, mixed>  $datos
     */
    public static function entradaRealizacion(string $idLabor, array $datos): RealizarLaborEntrada
    {
        return new RealizarLaborEntrada(
            idLabor: $idLabor,
            idOperacion: (string) $datos['idOperacion'],
            fechaCreacion: SolicitudEstricta::fechaHora((string) $datos['fechaCreacion']),
            fechaEjecucion: SolicitudEstricta::fechaHora((string) $datos['fechaEjecucion']),
            observaciones: self::texto($datos['observaciones'] ?? null),
            insumos: $datos['insumos'] ?? [],
        );
    }

    /** Laravel recorta y convierte en null los textos vacíos de una solicitud; dentro de un lote se hace aquí. */
    private static function texto(mixed $valor): ?string
    {
        $texto = is_string($valor) ? trim($valor) : null;

        return $texto === '' ? null : $texto;
    }

    public function resolver(ResolverRevisionRequest $request, string $id, ResolverRevisionCasoUso $resolver): JsonResponse
    {
        $labor = $resolver->ejecutar(new ResolverRevisionEntrada(
            idLabor: $id,
            decision: DecisionRevision::from((string) $request->input('decision')),
            observacion: (string) $request->input('observacion'),
            version: (int) $request->input('version'),
        ), self::usuario($request));

        return new JsonResponse(LaborRecurso::aArreglo($labor));
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
            'Location' => "/api/operaciones/v1/labores/{$resultado->labor->id}",
        ]);
    }

    private static function usuario(Request $request): UsuarioAutenticado
    {
        return $request->attributes->get(UsuarioAutenticado::class);
    }
}
