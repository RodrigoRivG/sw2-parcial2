<?php

namespace App\Application\Contracts;

use DateTimeImmutable;

interface Reloj
{
    /** Fecha y hora actual en UTC. */
    public function ahora(): DateTimeImmutable;
}
