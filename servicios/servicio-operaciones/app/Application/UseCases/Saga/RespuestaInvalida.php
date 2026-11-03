<?php

namespace App\Application\UseCases\Saga;

use RuntimeException;

/** La respuesta no se puede procesar con seguridad: va a la DLQ sin reintentos (RQ-SAG-08). */
final class RespuestaInvalida extends RuntimeException {}
