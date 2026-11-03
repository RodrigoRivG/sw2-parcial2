<?php

namespace App\Application\Contracts;

use RuntimeException;

/** El broker no confirmó la publicación. El estado ya está guardado: la tarea de recuperación reenvía. */
final class PublicacionFallida extends RuntimeException {}
