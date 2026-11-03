<?php

namespace App\Infrastructure\Persistence\DynamoDb;

use App\Application\Contracts\RegistroAuditoria;
use App\Application\Contracts\Reloj;
use Aws\DynamoDb\Marshaler;
use Illuminate\Support\Facades\Context;
use Illuminate\Support\Str;

final class RegistroAuditoriaDynamo implements RegistroAuditoria
{
    private readonly Marshaler $marshaler;

    public function __construct(
        private readonly UnidadTrabajoDynamo $unidadTrabajo,
        private readonly NombresTablas $tablas,
        private readonly Reloj $reloj,
    ) {
        $this->marshaler = new Marshaler;
    }

    public function registrar(string $actor, string $accion, string $entidad, string $idEntidad): void
    {
        $this->unidadTrabajo->agregar([
            'Put' => [
                'TableName' => $this->tablas->de('registros_auditoria'),
                'Item' => $this->marshaler->marshalItem([
                    'id' => (string) Str::uuid(),
                    'actor' => $actor,
                    'accion' => $accion,
                    'entidad' => $entidad,
                    'id_entidad' => $idEntidad,
                    'entidad_id' => "{$entidad}#{$idEntidad}",
                    'id_correlacion' => (string) Context::get('idCorrelacion', ''),
                    'fecha' => FormatoFecha::conHora($this->reloj->ahora()),
                ]),
            ],
        ], 'auditoria');
    }
}
