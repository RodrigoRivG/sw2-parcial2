<?php

namespace App\InterfaceAdapters\Http\Requests;

use App\Domain\FieldTask\DecisionRevision;
use Illuminate\Validation\Rule;

/**
 * Cuerpo de POST /labores/{id}/resolucion (spec-revision-labores.md RQ-REV-01).
 */
final class ResolverRevisionRequest extends SolicitudEstricta
{
    public function rules(): array
    {
        return [
            'decision' => ['required', 'string', Rule::enum(DecisionRevision::class)],
            'observacion' => ['required', 'string', 'max:500'],
            'version' => ['required', 'integer', 'min:0'],
        ];
    }
}
