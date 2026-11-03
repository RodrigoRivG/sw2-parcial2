<?php

namespace App\Application\Contracts;

/**
 * Bucket privado de fotografías (constitución §4). Solo se accede a un objeto con una URL prefirmada de corta duración.
 */
interface AlmacenamientoArchivos
{
    public function guardar(string $clave, string $contenido, string $tipoContenido): void;

    public function borrar(string $clave): void;

    public function urlTemporal(string $clave, int $minutos): UrlTemporal;
}
