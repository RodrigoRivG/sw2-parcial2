<?php

namespace App\Domain\Incident;

/**
 * Lo que se guarda de la foto: la clave del objeto en el bucket privado, nunca el binario ni una URL (constitución §4).
 */
final class ReferenciaFoto
{
    public function __construct(
        public readonly string $clave,
        public readonly string $tipoContenido,
        public readonly int $tamanio,
    ) {}
}
