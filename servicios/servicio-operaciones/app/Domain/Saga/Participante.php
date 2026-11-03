<?php

namespace App\Domain\Saga;

/** Servicio que ejecuta un paso; la infraestructura lo traduce a su cola de comandos. */
enum Participante: string
{
    case INVENTARIO = 'INVENTARIO';
    case GESTION = 'GESTION';
}
