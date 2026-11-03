<?php

namespace App\Domain\Saga;

use DateTimeImmutable;

/**
 * Detalle de un paso de la Saga (RQ-SAG-11, RNF-22).
 */
final class RegistroPaso
{
    /**
     * @param  array{tipo: string, codigo: ?string, motivo: ?string}|null  $respuesta
     */
    public function __construct(
        public private(set) EstadoPaso $estado,
        public private(set) int $intentos,
        public private(set) ?DateTimeImmutable $fechaPrimerEnvio,
        public private(set) ?DateTimeImmutable $fechaUltimoEnvio,
        public private(set) ?DateTimeImmutable $fechaRespuesta = null,
        public private(set) ?array $respuesta = null,
        public private(set) ?string $error = null,
    ) {}

    public static function enviado(DateTimeImmutable $ahora): self
    {
        return new self(EstadoPaso::ENVIADO, 1, $ahora, $ahora);
    }

    public static function omitido(DateTimeImmutable $ahora): self
    {
        return new self(EstadoPaso::OMITIDO, 0, null, null, $ahora);
    }

    public function reenviar(DateTimeImmutable $ahora): void
    {
        $this->intentos++;
        $this->fechaUltimoEnvio = $ahora;
    }

    public function responder(RespuestaSaga $respuesta, DateTimeImmutable $ahora): void
    {
        $this->estado = $respuesta->tipo->esRechazo() ? EstadoPaso::RECHAZADO : EstadoPaso::COMPLETADO;
        $this->fechaRespuesta = $ahora;
        $this->respuesta = ['tipo' => $respuesta->tipo->value, 'codigo' => $respuesta->codigo, 'motivo' => $respuesta->motivo];
    }

    public function agotar(string $error): void
    {
        $this->estado = EstadoPaso::SIN_RESPUESTA;
        $this->error = $error;
    }
}
