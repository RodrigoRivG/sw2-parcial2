<?php

namespace App\InterfaceAdapters\Http\Requests;

use DateTimeImmutable;
use DateTimeZone;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Validator;

/**
 * FormRequest que además rechaza los campos no declarados (spec-labores.md 2.2) y lee fechas UTC.
 */
abstract class SolicitudEstricta extends FormRequest
{
    /** Fecha y hora UTC, con o sin milisegundos (README D-04). */
    public const FECHA_HORA = 'date_format:Y-m-d\TH:i:s\Z,Y-m-d\TH:i:s.v\Z';

    /** Decimal como texto; el signo pasa a propósito para que el dominio responda 422 (README D-03). */
    public const DECIMAL_3 = 'regex:/^-?\d{1,12}(\.\d{1,3})?$/';

    public function authorize(): bool
    {
        return true;
    }

    public function after(): array
    {
        return [function (Validator $validator) {
            $permitidos = array_keys($this->rules());
            foreach (array_keys($this->all()) as $campo) {
                if (! in_array($campo, $permitidos, true)) {
                    $validator->errors()->add((string) $campo, 'El campo no está permitido.');
                }
            }
        }];
    }

    public static function fechaHora(string $texto): DateTimeImmutable
    {
        $utc = new DateTimeZone('UTC');

        return DateTimeImmutable::createFromFormat('!Y-m-d\TH:i:s.v\Z', $texto, $utc)
            ?: DateTimeImmutable::createFromFormat('!Y-m-d\TH:i:s\Z', $texto, $utc);
    }
}
