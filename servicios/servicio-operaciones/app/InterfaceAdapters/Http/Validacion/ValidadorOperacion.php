<?php

namespace App\InterfaceAdapters\Http\Validacion;

use App\Application\UseCases\SyncOfflineOperations\OperacionSincronizacion;
use App\Domain\Shared\ExcepcionDominio;
use App\Domain\Shared\Motivo;
use App\InterfaceAdapters\Http\Controllers\IncidenciaControlador;
use App\InterfaceAdapters\Http\Controllers\LaborControlador;
use App\InterfaceAdapters\Http\Requests\CrearLaborRequest;
use App\InterfaceAdapters\Http\Requests\RealizarLaborRequest;
use App\InterfaceAdapters\Http\Requests\RegistrarIncidenciaRequest;
use App\InterfaceAdapters\Http\Requests\SolicitudEstricta;
use DateTimeImmutable;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Validator;

/**
 * Lee una operación del lote con las mismas reglas de su endpoint (spec-sincronizacion.md RQ-SIN-04).
 */
final class ValidadorOperacion
{
    public const TIPOS = ['REGISTRAR_LABOR', 'REALIZAR_LABOR', 'REGISTRAR_INCIDENCIA'];

    /**
     * @param  array<string, UploadedFile>  $fotos  partes `fotos[<idOperacion>]`
     */
    public static function leer(int $indice, mixed $operacion, array $fotos): OperacionSincronizacion
    {
        $datos = is_array($operacion) && is_array($operacion['datos'] ?? null) ? self::normalizar($operacion['datos']) : null;
        $tipo = is_array($operacion) && in_array($operacion['tipo'] ?? null, self::TIPOS, true) ? $operacion['tipo'] : null;
        $idOperacion = is_string($datos['idOperacion'] ?? null) ? $datos['idOperacion'] : null;
        $fechaCreacion = is_string($datos['fechaCreacion'] ?? null) ? self::fecha($datos['fechaCreacion']) : null;

        $sobreValido = $tipo !== null && $datos !== null && $fechaCreacion !== null
            && $idOperacion !== null && preg_match('/^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$/', $idOperacion) === 1
            && array_diff(array_keys($operacion), ['tipo', 'datos']) === [];
        if (! $sobreValido) {
            return new OperacionSincronizacion($indice, is_string($operacion['tipo'] ?? null) ? $operacion['tipo'] : null, $idOperacion, null, null,
                new Motivo('DATOS_INVALIDOS', 'La operación no tiene tipo, idOperacion o fechaCreacion válidos.'));
        }

        $errores = match ($tipo) {
            'REGISTRAR_LABOR' => self::errores($datos, CrearLaborRequest::reglas()),
            'REALIZAR_LABOR' => self::errores($datos, [...RealizarLaborRequest::reglas(), 'idLabor' => ['required', 'uuid']]),
            'REGISTRAR_INCIDENCIA' => RegistrarIncidenciaRequest::erroresDatos($datos),
        };
        $foto = $fotos[$idOperacion] ?? null;
        if ($tipo === 'REGISTRAR_INCIDENCIA' && ! $foto instanceof UploadedFile) {
            $errores["fotos[{$idOperacion}]"][] = 'Falta la foto de la incidencia.';
        }
        if ($errores !== []) {
            return new OperacionSincronizacion($indice, $tipo, $idOperacion, $fechaCreacion, null,
                new Motivo('DATOS_INVALIDOS', 'Los datos de la operación no son válidos.', self::detalles($errores)));
        }

        try {
            $entrada = match ($tipo) {
                'REGISTRAR_LABOR' => LaborControlador::entradaCreacion($datos),
                'REALIZAR_LABOR' => LaborControlador::entradaRealizacion((string) $datos['idLabor'], array_diff_key($datos, ['idLabor' => true])),
                'REGISTRAR_INCIDENCIA' => IncidenciaControlador::entrada($datos, $foto),
            };
        } catch (ExcepcionDominio $e) {
            // Por ejemplo, una foto que PHP no aceptó por tamaño: FOTO_INVALIDA, igual que en POST /incidencias
            return new OperacionSincronizacion($indice, $tipo, $idOperacion, $fechaCreacion, null, new Motivo($e->codigo, $e->getMessage(), $e->detalles));
        }

        return new OperacionSincronizacion($indice, $tipo, $idOperacion, $fechaCreacion, $entrada);
    }

    /**
     * Lo mismo que TrimStrings y ConvertEmptyStringsToNull hacen con el cuerpo de una solicitud normal.
     *
     * @param  array<mixed>  $datos
     * @return array<mixed>
     */
    private static function normalizar(array $datos): array
    {
        return array_map(function (mixed $valor) {
            if (is_array($valor)) {
                return self::normalizar($valor);
            }
            if (is_string($valor)) {
                $valor = trim($valor);

                return $valor === '' ? null : $valor;
            }

            return $valor;
        }, $datos);
    }

    private static function fecha(string $texto): ?DateTimeImmutable
    {
        return Validator::make(['f' => $texto], ['f' => [SolicitudEstricta::FECHA_HORA]])->fails() ? null : SolicitudEstricta::fechaHora($texto);
    }

    /**
     * @param  array<string, mixed>  $datos
     * @param  array<string, mixed>  $reglas
     * @return array<string, list<string>>
     */
    private static function errores(array $datos, array $reglas): array
    {
        $errores = Validator::make($datos, $reglas)->errors()->toArray();
        foreach (array_keys($datos) as $campo) {
            if (! array_key_exists($campo, $reglas)) {
                $errores[$campo][] = 'El campo no está permitido.';
            }
        }

        return $errores;
    }

    /**
     * @param  array<string, list<string>>  $errores
     * @return list<array{campo: string, mensaje: string}>
     */
    private static function detalles(array $errores): array
    {
        $detalles = [];
        foreach ($errores as $campo => $mensajes) {
            foreach ($mensajes as $mensaje) {
                $detalles[] = ['campo' => (string) $campo, 'mensaje' => $mensaje];
            }
        }

        return $detalles;
    }
}
