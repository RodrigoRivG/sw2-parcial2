<?php

namespace App\Infrastructure\Persistence\DynamoDb;

use App\Application\Contracts\CursorInvalido;

/**
 * LastEvaluatedKey de DynamoDB ↔ cursor opaco en base64url (README D-05).
 */
final class CodificadorCursor
{
    /**
     * @param  array<string, array<string, string>>|null  $ultimaClave
     */
    public static function codificar(?array $ultimaClave): ?string
    {
        if ($ultimaClave === null || $ultimaClave === []) {
            return null;
        }

        return rtrim(strtr(base64_encode(json_encode($ultimaClave, JSON_THROW_ON_ERROR)), '+/', '-_'), '=');
    }

    /**
     * @param  list<string>  $atributosClave  atributos que debe tener la clave del índice usado
     * @param  array<string, string>  $valoresFijos  atributos cuyo valor debe coincidir con el filtro actual (la partición)
     * @return array<string, array<string, string>>
     */
    public static function decodificar(string $cursor, array $atributosClave, array $valoresFijos): array
    {
        $json = base64_decode(strtr($cursor, '-_', '+/'), true);
        $clave = $json === false ? null : json_decode($json, true);
        if (! is_array($clave)) {
            throw new CursorInvalido;
        }

        $nombres = array_keys($clave);
        sort($nombres);
        $esperados = $atributosClave;
        sort($esperados);
        if ($nombres !== $esperados) {
            throw new CursorInvalido;
        }
        foreach ($clave as $valor) {
            if (! is_array($valor) || array_keys($valor) !== ['S'] || ! is_string($valor['S'])) {
                throw new CursorInvalido;
            }
        }
        foreach ($valoresFijos as $atributo => $valor) {
            if ($clave[$atributo]['S'] !== $valor) {
                throw new CursorInvalido;
            }
        }

        return $clave;
    }
}
