<?php

namespace App\Domain\Saga;

use App\Domain\FieldTask\EstadoLabor;
use App\Domain\Shared\Motivo;

/**
 * Qué hacer después de aplicar una respuesta o un vencimiento: cambio de la labor y comando a enviar.
 */
final class Decision
{
    public function __construct(
        public readonly ?EstadoLabor $estadoLabor = null,
        public readonly ?Motivo $motivoLabor = null,
        public readonly ?PasoSaga $pasoAEnviar = null,
        public readonly bool $tardia = false,
    ) {}

    public function cambiaLabor(): bool
    {
        return $this->estadoLabor !== null || $this->motivoLabor !== null;
    }
}
