<?php

use Illuminate\Support\Facades\Route;

/**
 * Lee las rutas y respuestas de openapi.yaml sin un parser de YAML: el archivo usa indentación fija
 * (2 espacios para la ruta, 4 para el método, 8 para cada código de respuesta).
 *
 * @return array<string, list<string>> "GET /ruta" => códigos de respuesta documentados
 */
function operacionesDocumentadas(): array
{
    $operaciones = [];
    $ruta = null;
    $operacion = null;
    $enPaths = false;

    foreach (file(base_path('openapi.yaml'), FILE_IGNORE_NEW_LINES) as $linea) {
        if (preg_match('/^(\w+):/', $linea, $m) === 1) {
            $enPaths = $m[1] === 'paths';

            continue;
        }
        if (! $enPaths) {
            continue;
        }
        if (preg_match('#^  (/\S*):\s*$#', $linea, $m) === 1) {
            $ruta = $m[1];
        } elseif ($ruta !== null && preg_match('/^    (get|post|put|delete|patch):\s*$/', $linea, $m) === 1) {
            $operacion = strtoupper($m[1]).' '.$ruta;
            $operaciones[$operacion] = [];
        } elseif ($operacion !== null && preg_match("/^        '(\d{3})':/", $linea, $m) === 1) {
            $operaciones[$operacion][] = $m[1];
        }
    }

    return $operaciones;
}

it('documenta toda ruta de la API con sus errores de autenticación y permisos', function () {
    $documentadas = operacionesDocumentadas();
    $faltantes = [];

    foreach (Route::getRoutes() as $ruta) {
        $uri = '/'.ltrim($ruta->uri(), '/');
        foreach (array_diff($ruta->methods(), ['HEAD']) as $metodo) {
            $clave = "{$metodo} {$uri}";
            if (! array_key_exists($clave, $documentadas)) {
                $faltantes[] = "{$clave}: no está en openapi.yaml";

                continue;
            }
            $protegida = str_starts_with($uri, '/api/operaciones/v1/');
            if ($protegida && array_diff(['401', '403'], $documentadas[$clave]) !== []) {
                $faltantes[] = "{$clave}: faltan las respuestas 401 o 403";
            }
        }
    }

    expect($faltantes)->toBe([]);
});
