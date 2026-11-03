<?php

namespace App\InterfaceAdapters\Http\Requests;

use App\Domain\FieldTask\TipoLabor;
use Illuminate\Validation\Rule;

/**
 * Cuerpo de POST /labores (spec-labores.md RQ-LAB-01): exactamente una de fechaProgramada o fechaEjecucion.
 */
final class CrearLaborRequest extends SolicitudEstricta
{
    public function rules(): array
    {
        return self::reglas();
    }

    /**
     * Reglas de POST /labores; las reutiliza la sincronización (spec-sincronizacion.md T01).
     *
     * @return array<string, mixed>
     */
    public static function reglas(): array
    {
        return [
            'idOperacion' => ['required', 'uuid'],
            'fechaCreacion' => ['required', 'string', self::FECHA_HORA],
            'tipoLabor' => ['required', 'string', Rule::enum(TipoLabor::class)],
            'idParcela' => ['required', 'uuid'],
            'idCampania' => ['required', 'uuid'],
            'fechaProgramada' => ['required_without:fechaEjecucion', 'prohibits:fechaEjecucion,insumos', 'string', 'date_format:Y-m-d'],
            'fechaEjecucion' => ['required_without:fechaProgramada', 'string', self::FECHA_HORA],
            'observaciones' => ['nullable', 'string', 'max:500'],
            'insumos' => ['sometimes', 'array', 'list', 'max:20'],
            'insumos.*' => ['array:idInsumo,cantidad'],
            'insumos.*.idInsumo' => ['required', 'uuid', 'distinct:ignore_case'],
            'insumos.*.cantidad' => ['required', 'string', self::DECIMAL_3],
        ];
    }

    public function esProgramacion(): bool
    {
        return $this->filled('fechaProgramada');
    }
}
