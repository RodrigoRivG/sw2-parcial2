<?php

namespace App\InterfaceAdapters\Messaging;

/**
 * Sobre común de mensajería (constitución §10). Si no se puede interpretar, el mensaje va a la DLQ.
 */
final class SobreMensaje
{
    /**
     * @param  array<string, mixed>  $datos
     */
    private function __construct(
        public readonly string $idMensaje,
        public readonly string $idCorrelacion,
        public readonly string $tipo,
        public readonly mixed $version,
        public readonly array $datos,
    ) {}

    /**
     * @return self|string el sobre, o el motivo por el que no se puede interpretar
     */
    public static function interpretar(string $cuerpo): self|string
    {
        $json = json_decode($cuerpo, true);
        if (! is_array($json)) {
            return 'El cuerpo no es un JSON válido.';
        }
        foreach (['idMensaje', 'idCorrelacion', 'tipo'] as $campo) {
            if (! is_string($json[$campo] ?? null) || $json[$campo] === '') {
                return "Falta {$campo} en el sobre.";
            }
        }
        if (preg_match('/^[0-9a-fA-F-]{36}$/', $json['idMensaje']) !== 1 || preg_match('/^[0-9a-fA-F-]{36}$/', $json['idCorrelacion']) !== 1) {
            return 'idMensaje e idCorrelacion deben ser UUID.';
        }
        if (! is_array($json['datos'] ?? null)) {
            return 'Falta datos en el sobre.';
        }

        return new self($json['idMensaje'], $json['idCorrelacion'], $json['tipo'], $json['version'] ?? null, $json['datos']);
    }
}
