<?php

namespace App\Domain\Shared;

/**
 * Cantidad de un insumo: texto decimal > 0 con hasta 3 decimales, normalizado a escala 3 (README D-01).
 * Se opera con bcmath, nunca con float (README D-03).
 */
final class Cantidad
{
    private const ESCALA = 3;

    private function __construct(public readonly string $valor) {}

    public static function desdeTexto(string $texto): self
    {
        if (preg_match('/^-?\d{1,12}(\.\d{1,3})?$/', $texto) !== 1) {
            throw self::invalida();
        }
        $normalizada = bcadd($texto, '0', self::ESCALA);
        if (bccomp($normalizada, '0', self::ESCALA) <= 0) {
            throw self::invalida();
        }

        return new self($normalizada);
    }

    public function esIgualA(self $otra): bool
    {
        return bccomp($this->valor, $otra->valor, self::ESCALA) === 0;
    }

    private static function invalida(): ExcepcionDominio
    {
        return ExcepcionDominio::reglaNegocio('CANTIDAD_INVALIDA', 'La cantidad de cada insumo debe ser mayor a 0, con hasta 3 decimales.');
    }
}
