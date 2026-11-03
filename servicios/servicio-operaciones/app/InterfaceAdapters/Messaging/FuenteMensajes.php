<?php

namespace App\InterfaceAdapters\Messaging;

/**
 * Cola de la que se consumen las respuestas de la Saga. La implementa la infraestructura (RabbitMQ).
 */
interface FuenteMensajes
{
    /**
     * Entrega cada mensaje, de a uno, al manejador. Si el manejador devuelve null, el mensaje se confirma;
     * si devuelve un motivo, se publica en la DLQ con ese motivo y luego se confirma (README D-13).
     *
     * @param  callable(string): ?string  $manejador
     * @param  int|null  $maximo  termina después de procesar esta cantidad (tests)
     * @param  float|null  $segundosSinMensajes  termina si no llega nada en este tiempo (tests)
     * @return int mensajes procesados
     */
    public function consumir(callable $manejador, ?int $maximo = null, ?float $segundosSinMensajes = null): int;
}
