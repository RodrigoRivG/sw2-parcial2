<?php

namespace App\Domain\Saga;

/**
 * Lo que la Saga necesita de una respuesta, ya validada y traducida desde el mensaje.
 */
final class RespuestaSaga
{
    /**
     * @param  list<array<string, mixed>>  $detalles  insumos afectados de un rechazo de inventario
     */
    public function __construct(
        public readonly TipoRespuesta $tipo,
        public readonly string $idMensaje,
        public readonly ?string $codigo = null,
        public readonly ?string $motivo = null,
        public readonly ?string $costoTotal = null,
        public readonly array $detalles = [],
    ) {}
}
