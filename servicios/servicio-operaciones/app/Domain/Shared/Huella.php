<?php

namespace App\Domain\Shared;

/**
 * SHA-256 del contenido de una operación más el usuario que la envía (README D-06).
 * Dos envíos con los mismos datos en otro orden o con otros espacios dan la misma huella.
 */
final class Huella
{
    /**
     * @param  array<string, mixed>  $contenido  ya normalizado por quien la calcula (cantidades, fechas)
     */
    public static function calcular(array $contenido, string $idUsuario): string
    {
        $canonico = self::ordenar(['contenido' => $contenido, 'usuario' => $idUsuario]);

        return hash('sha256', json_encode($canonico, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));
    }

    private static function ordenar(mixed $valor): mixed
    {
        if (is_string($valor)) {
            return trim($valor);
        }
        if (! is_array($valor)) {
            return $valor;
        }
        $ordenado = array_map(self::ordenar(...), $valor);
        if (! array_is_list($ordenado)) {
            ksort($ordenado);
        }

        return $ordenado;
    }
}
