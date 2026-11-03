<?php

namespace App\InterfaceAdapters\Http\Requests;

/**
 * Cuerpo de POST /labores/{id}/realizacion (spec-labores.md RQ-LAB-07).
 */
final class RealizarLaborRequest extends SolicitudEstricta
{
    public function rules(): array
    {
        return self::reglas();
    }

    /**
     * Reglas de la realización; las reutiliza la sincronización (spec-sincronizacion.md T01).
     *
     * @return array<string, mixed>
     */
    public static function reglas(): array
    {
        return [
            'idOperacion' => ['required', 'uuid'],
            'fechaCreacion' => ['required', 'string', self::FECHA_HORA],
            'fechaEjecucion' => ['required', 'string', self::FECHA_HORA],
            'observaciones' => ['nullable', 'string', 'max:500'],
            'insumos' => ['sometimes', 'array', 'list', 'max:20'],
            'insumos.*' => ['array:idInsumo,cantidad'],
            'insumos.*.idInsumo' => ['required', 'uuid', 'distinct:ignore_case'],
            'insumos.*.cantidad' => ['required', 'string', self::DECIMAL_3],
        ];
    }
}
