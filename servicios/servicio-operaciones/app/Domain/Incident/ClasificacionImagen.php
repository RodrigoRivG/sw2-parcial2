<?php

namespace App\Domain\Incident;

use App\Domain\Shared\ExcepcionDominio;

/**
 * Resultado de clasificar la fotografía, que este servicio solo guarda. Siempre orientativo (RN-13).
 */
final class ClasificacionImagen
{
    private function __construct(
        public readonly string $categoria,
        public readonly string $confianza,
        public readonly string $versionModelo,
        public readonly OrigenClasificacion $origen,
    ) {}

    public static function crear(string $categoria, string $confianza, string $versionModelo, OrigenClasificacion $origen): self
    {
        if (preg_match('/^-?\d+(\.\d{1,4})?$/', $confianza) !== 1
            || bccomp($confianza, '0', 4) < 0 || bccomp($confianza, '1', 4) > 0) {
            throw ExcepcionDominio::reglaNegocio('CONFIANZA_INVALIDA', 'La confianza de la clasificación debe estar entre 0 y 1.');
        }

        return new self(trim($categoria), bcadd($confianza, '0', 4), trim($versionModelo), $origen);
    }
}
