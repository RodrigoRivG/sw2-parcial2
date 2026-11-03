<?php

namespace App\Infrastructure\Messaging;

use App\Domain\Saga\Participante;
use PhpAmqpLib\Channel\AMQPChannel;
use PhpAmqpLib\Wire\AMQPTable;

/**
 * Colas de la Saga (spec-saga.md 2.2, README D-13). Las de los participantes se declaran con sus mismos
 * argumentos: un argumento distinto haría fallar la declaración (PRECONDITION_FAILED).
 */
final class TopologiaSaga
{
    public const COLA_INVENTARIO = 'servicio-inventario.comandos';

    public const COLA_GESTION = 'servicio-gestion.comandos';

    public const COLA_RESPUESTAS = 'servicio-operaciones.respuestas-saga';

    public const COLA_RESPUESTAS_DLQ = 'servicio-operaciones.respuestas-saga.dlq';

    public static function colaDe(Participante $participante): string
    {
        return match ($participante) {
            Participante::INVENTARIO => self::COLA_INVENTARIO,
            Participante::GESTION => self::COLA_GESTION,
        };
    }

    public static function declarar(AMQPChannel $canal): void
    {
        foreach ([self::COLA_INVENTARIO, self::COLA_GESTION] as $cola) {
            $canal->queue_declare($cola, false, true, false, false, false, new AMQPTable([
                'x-dead-letter-exchange' => '',
                'x-dead-letter-routing-key' => "{$cola}.dlq",
            ]));
        }
        // Sin argumentos: así la declaran inventario y gestión, que también publican aquí
        $canal->queue_declare(self::COLA_RESPUESTAS, false, true, false, false);
        $canal->queue_declare(self::COLA_RESPUESTAS_DLQ, false, true, false, false);
    }
}
