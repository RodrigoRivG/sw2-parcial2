<?php

namespace App\InterfaceAdapters\Http\Requests;

use App\Application\UseCases\QueryIncidents\FiltroIncidencias;
use App\Domain\Incident\TipoIncidencia;
use Illuminate\Validation\Rule;
use Illuminate\Validation\Validator;

/**
 * Parámetros de GET /incidencias (spec-incidencias.md RQ-INC-09).
 */
final class ListarIncidenciasRequest extends SolicitudEstricta
{
    public function rules(): array
    {
        return [
            'idParcela' => ['sometimes', 'uuid'],
            'idCampania' => ['sometimes', 'uuid'],
            'mias' => ['sometimes', 'in:true,false'],
            'tipo' => ['sometimes', Rule::enum(TipoIncidencia::class)],
            'fechaDesde' => ['sometimes', 'date_format:Y-m-d'],
            'fechaHasta' => ['sometimes', 'date_format:Y-m-d', 'after_or_equal:fechaDesde'],
            'orden' => ['sometimes', 'in:ASC,DESC'],
            'limite' => ['sometimes', 'integer', 'min:1', 'max:100'],
            'cursor' => ['sometimes', 'string', 'max:2000'],
        ];
    }

    public function after(): array
    {
        return [
            ...parent::after(),
            function (Validator $validator) {
                if (! $this->has('idParcela') && ! $this->has('idCampania') && ! $this->mias()) {
                    $validator->errors()->add('filtro', 'Indique idParcela, idCampania o mias=true.');
                }
            },
        ];
    }

    public function mias(): bool
    {
        return $this->query('mias') === 'true';
    }

    public function filtro(): FiltroIncidencias
    {
        $tipo = $this->query('tipo');

        return new FiltroIncidencias(
            idParcela: $this->has('idParcela') ? strtolower((string) $this->query('idParcela')) : null,
            idCampania: $this->has('idCampania') ? strtolower((string) $this->query('idCampania')) : null,
            tipo: $tipo === null ? null : TipoIncidencia::from((string) $tipo),
            fechaDesde: $this->query('fechaDesde'),
            fechaHasta: $this->query('fechaHasta'),
            ascendente: $this->query('orden') === 'ASC',
            limite: (int) $this->query('limite', 20),
            cursor: $this->query('cursor'),
        );
    }
}
