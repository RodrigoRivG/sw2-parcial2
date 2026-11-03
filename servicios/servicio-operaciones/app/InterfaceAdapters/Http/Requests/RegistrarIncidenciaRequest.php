<?php

namespace App\InterfaceAdapters\Http\Requests;

use App\Domain\Incident\OrigenClasificacion;
use App\Domain\Incident\TipoIncidencia;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Validator as Validadores;
use Illuminate\Validation\Rule;
use Illuminate\Validation\Validator;

/**
 * POST /incidencias (`multipart/form-data`): la parte `datos` es JSON y la parte `foto`, el archivo (RQ-INC-01).
 */
final class RegistrarIncidenciaRequest extends FormRequest
{
    /** @var array<string, mixed>|null */
    private ?array $datosDecodificados = null;

    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'datos' => ['required', 'string'],
            'foto' => ['required'],
        ];
    }

    /**
     * Reglas de la parte `datos`; las reutiliza la sincronización (spec-sincronizacion.md T01).
     *
     * @return array<string, mixed>
     */
    public static function reglasDatos(): array
    {
        return [
            'idOperacion' => ['required', 'uuid'],
            'fechaCreacion' => ['required', 'string', SolicitudEstricta::FECHA_HORA],
            'tipo' => ['required', 'string', Rule::enum(TipoIncidencia::class)],
            'descripcion' => ['required', 'string', 'max:1000', 'regex:/\S/'],
            'fechaObservacion' => ['required', 'string', SolicitudEstricta::FECHA_HORA],
            'idParcela' => ['required', 'uuid'],
            'idCampania' => ['nullable', 'uuid'],
            'clasificacion' => ['nullable', 'array:categoria,confianza,versionModelo,origen'],
            'clasificacion.categoria' => ['required_with:clasificacion', 'string', 'max:100', 'regex:/\S/'],
            // El rango (0 a 1) lo valida el dominio: 422 CONFIANZA_INVALIDA
            'clasificacion.confianza' => ['required_with:clasificacion', 'string', 'regex:/^-?\d{1,3}(\.\d{1,4})?$/'],
            'clasificacion.versionModelo' => ['required_with:clasificacion', 'string', 'max:50', 'regex:/\S/'],
            'clasificacion.origen' => ['required_with:clasificacion', 'string', Rule::enum(OrigenClasificacion::class)],
        ];
    }

    public function after(): array
    {
        return [function (Validator $validator) {
            foreach (array_keys($this->all()) as $campo) {
                if (! in_array($campo, ['datos', 'foto'], true)) {
                    $validator->errors()->add((string) $campo, 'El campo no está permitido.');
                }
            }
            if ($this->has('foto') && ! $this->file('foto') instanceof UploadedFile) {
                $validator->errors()->add('foto', 'La foto debe enviarse como archivo.');
            }
            if (! is_string($this->input('datos'))) {
                return;
            }

            $datos = json_decode($this->input('datos'), true);
            if (! is_array($datos) || array_is_list($datos)) {
                $validator->errors()->add('datos', 'La parte datos debe ser un objeto JSON.');

                return;
            }
            foreach (self::erroresDatos($datos) as $campo => $mensajes) {
                foreach ($mensajes as $mensaje) {
                    $validator->errors()->add("datos.{$campo}", $mensaje);
                }
            }
            $this->datosDecodificados = $datos;
        }];
    }

    /**
     * @param  array<string, mixed>  $datos
     * @return array<string, list<string>>
     */
    public static function erroresDatos(array $datos): array
    {
        $validador = Validadores::make($datos, self::reglasDatos());
        $errores = $validador->errors()->toArray();
        foreach (array_keys($datos) as $campo) {
            if (! array_key_exists($campo, self::reglasDatos())) {
                $errores[$campo][] = 'El campo no está permitido.';
            }
        }

        return $errores;
    }

    /** @return array<string, mixed> */
    public function datos(): array
    {
        return (array) $this->datosDecodificados;
    }
}
