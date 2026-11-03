<?php

namespace App\InterfaceAdapters\Http\Controllers;

use App\Application\Contracts\AlmacenamientoArchivos;
use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\QueryIncidents\ConsultarIncidenciasCasoUso;
use App\Application\UseCases\QueryIncidents\IncidenciaConFoto;
use App\Application\UseCases\RegisterIncident\RegistrarIncidenciaCasoUso;
use App\Application\UseCases\RegisterIncident\RegistrarIncidenciaEntrada;
use App\Domain\Incident\FotoIncidencia;
use App\Domain\Incident\OrigenClasificacion;
use App\Domain\Incident\TipoIncidencia;
use App\InterfaceAdapters\Http\Requests\ListarIncidenciasRequest;
use App\InterfaceAdapters\Http\Requests\RegistrarIncidenciaRequest;
use App\InterfaceAdapters\Http\Requests\SolicitudEstricta;
use App\InterfaceAdapters\Http\Resources\IncidenciaRecurso;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Context;

final class IncidenciaControlador
{
    public function crear(RegistrarIncidenciaRequest $request, RegistrarIncidenciaCasoUso $registrar, AlmacenamientoArchivos $almacenamiento): JsonResponse
    {
        $resultado = $registrar->ejecutar(self::entrada($request->datos(), $request->file('foto')), self::usuario($request));
        $conFoto = new IncidenciaConFoto($resultado->incidencia, $almacenamiento->urlTemporal($resultado->incidencia->foto->clave, ConsultarIncidenciasCasoUso::MINUTOS_URL));

        if ($resultado->repetida) {
            return new JsonResponse(IncidenciaRecurso::aArreglo($conFoto));
        }

        return new JsonResponse(IncidenciaRecurso::aArreglo($conFoto), 201, [
            'Location' => url("/api/operaciones/v1/incidencias/{$resultado->incidencia->id}"),
        ]);
    }

    public function listar(ListarIncidenciasRequest $request, ConsultarIncidenciasCasoUso $consultar): JsonResponse
    {
        $pagina = $consultar->listar($request->filtro(), $request->mias(), self::usuario($request));

        return new JsonResponse([
            'items' => array_map(fn (IncidenciaConFoto $i) => IncidenciaRecurso::aArreglo($i), $pagina->items),
            'siguienteCursor' => $pagina->siguienteCursor,
        ]);
    }

    public function detalle(Request $request, string $id, ConsultarIncidenciasCasoUso $consultar): JsonResponse
    {
        return new JsonResponse(IncidenciaRecurso::aArreglo($consultar->detalle($id, self::usuario($request))));
    }

    /**
     * Convierte la parte `datos` ya validada y la foto en la entrada del caso de uso. La usa también la sincronización.
     *
     * @param  array<string, mixed>  $datos
     */
    public static function entrada(array $datos, ?UploadedFile $foto): RegistrarIncidenciaEntrada
    {
        // Una foto que PHP rechazó por tamaño llega sin contenido: es una foto inválida, no un formato inválido
        if ($foto === null || ! $foto->isValid()) {
            throw FotoIncidencia::invalida();
        }
        $clasificacion = $datos['clasificacion'] ?? null;

        return new RegistrarIncidenciaEntrada(
            idOperacion: (string) $datos['idOperacion'],
            fechaCreacion: SolicitudEstricta::fechaHora((string) $datos['fechaCreacion']),
            tipo: TipoIncidencia::from((string) $datos['tipo']),
            descripcion: (string) $datos['descripcion'],
            fechaObservacion: SolicitudEstricta::fechaHora((string) $datos['fechaObservacion']),
            idParcela: (string) $datos['idParcela'],
            idCampania: isset($datos['idCampania']) ? (string) $datos['idCampania'] : null,
            clasificacion: $clasificacion === null ? null : [
                'categoria' => (string) $clasificacion['categoria'],
                'confianza' => (string) $clasificacion['confianza'],
                'versionModelo' => (string) $clasificacion['versionModelo'],
                'origen' => OrigenClasificacion::from((string) $clasificacion['origen']),
            ],
            contenidoFoto: (string) file_get_contents($foto->getRealPath()),
            idCorrelacion: (string) Context::get('idCorrelacion', ''),
        );
    }

    private static function usuario(Request $request): UsuarioAutenticado
    {
        return $request->attributes->get(UsuarioAutenticado::class);
    }
}
