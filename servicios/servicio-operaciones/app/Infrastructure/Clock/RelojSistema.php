<?php

namespace App\Infrastructure\Clock;

use App\Application\Contracts\Reloj;
use DateTimeImmutable;
use DateTimeZone;

final class RelojSistema implements Reloj
{
    public function ahora(): DateTimeImmutable
    {
        return new DateTimeImmutable('now', new DateTimeZone('UTC'));
    }
}
