<?php

namespace App\Application\Contracts;

use DateTimeImmutable;

final class UrlTemporal
{
    public function __construct(
        public readonly string $url,
        public readonly DateTimeImmutable $expiraEn,
    ) {}
}
