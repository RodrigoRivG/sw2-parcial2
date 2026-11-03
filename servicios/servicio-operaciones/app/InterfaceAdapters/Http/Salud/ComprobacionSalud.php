<?php

namespace App\InterfaceAdapters\Http\Salud;

/**
 * Una dependencia que readiness debe verificar (DynamoDB y, desde spec-saga.md, RabbitMQ).
 */
interface ComprobacionSalud
{
    public function nombre(): string;

    /** Lanza una excepción si la dependencia no responde. */
    public function comprobar(): void;
}
