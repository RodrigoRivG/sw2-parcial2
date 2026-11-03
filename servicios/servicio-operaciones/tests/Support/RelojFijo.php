<?php

namespace Tests\Support;

use App\Application\Contracts\Reloj;
use DateTimeImmutable;
use DateTimeZone;

final class RelojFijo implements Reloj
{
    private DateTimeImmutable $ahora;

    public function __construct(string $ahora = '2026-11-02T14:00:00Z')
    {
        $this->ahora = new DateTimeImmutable($ahora, new DateTimeZone('UTC'));
    }

    public function ahora(): DateTimeImmutable
    {
        return $this->ahora;
    }

    public function avanzar(string $intervalo): void
    {
        $this->ahora = $this->ahora->modify($intervalo);
    }
}
