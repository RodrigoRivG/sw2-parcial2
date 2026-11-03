<?php

namespace App\Infrastructure\Messaging;

use App\InterfaceAdapters\Http\Salud\ComprobacionSalud;

final class ComprobacionRabbitMq implements ComprobacionSalud
{
    public function nombre(): string
    {
        return 'rabbitmq';
    }

    public function comprobar(): void
    {
        ConexionRabbitMq::abrir(tiempoLimite: 2.0)->close();
    }
}
