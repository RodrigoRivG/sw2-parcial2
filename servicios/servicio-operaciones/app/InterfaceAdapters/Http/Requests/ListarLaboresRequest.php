<?php

namespace App\InterfaceAdapters\Http\Requests;

use App\Application\UseCases\QueryFieldTasks\FiltroLabores;
use App\Domain\FieldTask\EstadoLabor;
use Illuminate\Validation\Rule;
use Illuminate\Validation\Validator;

/**
 * Parámetros de GET /labores (spec-labores.md RQ-LAB-14).
 */
final class ListarLaboresRequest extends SolicitudEstricta
{
    public function rules(): array
    {
        return [
            'idCampania' => ['sometimes', 'uuid'],
            'idResponsable' => ['sometimes', 'string', 'max:100'],
            'mias' => ['sometimes', 'in:true,false'],
            'estado' => ['sometimes', Rule::enum(EstadoLabor::class)],
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
                if (! $this->has('idCampania') && ! $this->has('idResponsable') && ! $this->has('estado') && ! $this->mias()) {
                    $validator->errors()->add('filtro', 'Indique idCampania, idResponsable, mias=true o estado.');
                }
            },
        ];
    }

    public function mias(): bool
    {
        return $this->query('mias') === 'true';
    }

    public function filtro(): FiltroLabores
    {
        $estado = $this->query('estado');

        return new FiltroLabores(
            idCampania: $this->has('idCampania') ? strtolower((string) $this->query('idCampania')) : null,
            idResponsable: $this->has('idResponsable') ? (string) $this->query('idResponsable') : null,
            estado: $estado === null ? null : EstadoLabor::from((string) $estado),
            fechaDesde: $this->query('fechaDesde'),
            fechaHasta: $this->query('fechaHasta'),
            ascendente: $this->query('orden') === 'ASC',
            limite: (int) $this->query('limite', 20),
            cursor: $this->query('cursor'),
        );
    }
}
