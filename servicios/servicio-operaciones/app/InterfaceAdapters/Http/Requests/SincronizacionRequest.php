<?php

namespace App\InterfaceAdapters\Http\Requests;

use App\Application\UseCases\SyncOfflineOperations\OperacionSincronizacion;
use App\InterfaceAdapters\Http\Validacion\ValidadorOperacion;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Http\UploadedFile;
use Illuminate\Validation\Validator;

/**
 * POST /sincronizacion (`multipart/form-data`): la parte `operaciones` (lista JSON de 1 a 50) y una parte
 * `fotos[<idOperacion>]` por incidencia (spec-sincronizacion.md RQ-SIN-01). Un lote mal formado es 400 entero;
 * los errores de cada operación van en su resultado.
 */
final class SincronizacionRequest extends FormRequest
{
    public const MAXIMO_OPERACIONES = 50;

    /** @var list<mixed> */
    private array $lista = [];

    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'operaciones' => ['required', 'string'],
            'fotos' => ['sometimes', 'array'],
            'fotos.*' => ['file'],
        ];
    }

    public function after(): array
    {
        return [function (Validator $validator) {
            foreach (array_keys($this->all()) as $campo) {
                if (! in_array($campo, ['operaciones', 'fotos'], true)) {
                    $validator->errors()->add((string) $campo, 'El campo no está permitido.');
                }
            }
            if (! is_string($this->input('operaciones'))) {
                return;
            }
            $lista = json_decode($this->input('operaciones'), true);
            if (! is_array($lista) || ! array_is_list($lista) || $lista === [] || count($lista) > self::MAXIMO_OPERACIONES) {
                $validator->errors()->add('operaciones', 'Debe ser una lista JSON de 1 a '.self::MAXIMO_OPERACIONES.' operaciones.');

                return;
            }
            $this->lista = $lista;
        }];
    }

    /**
     * @return list<OperacionSincronizacion>
     */
    public function operaciones(): array
    {
        $fotos = array_filter((array) $this->file('fotos', []), fn ($foto) => $foto instanceof UploadedFile);

        return array_map(
            fn (mixed $operacion, int $indice) => ValidadorOperacion::leer($indice, $operacion, $fotos),
            $this->lista,
            array_keys($this->lista),
        );
    }
}
