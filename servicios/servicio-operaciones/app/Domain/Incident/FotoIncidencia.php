<?php

namespace App\Domain\Incident;

use App\Domain\Shared\ExcepcionDominio;

/**
 * Fotografía recibida (spec-incidencias.md RQ-INC-02): JPEG o PNG según su firma, de 1 byte a 10 MB.
 * Lo que manda es el contenido, no la extensión ni el tipo que declara el cliente.
 */
final class FotoIncidencia
{
    /** 10 MB: el mismo límite que `upload_max_filesize = 10M` de PHP. */
    public const TAMANIO_MAXIMO = 10 * 1024 * 1024;

    private const FIRMAS = [
        "\xFF\xD8\xFF" => ['image/jpeg', 'jpg'],
        "\x89PNG\r\n\x1A\n" => ['image/png', 'png'],
    ];

    private function __construct(
        public readonly string $contenido,
        public readonly string $tipoContenido,
        public readonly string $extension,
        public readonly string $sha256,
    ) {}

    public static function desdeContenido(string $contenido): self
    {
        $tamanio = strlen($contenido);
        if ($tamanio === 0 || $tamanio > self::TAMANIO_MAXIMO) {
            throw self::invalida();
        }
        foreach (self::FIRMAS as $firma => [$tipo, $extension]) {
            if (str_starts_with($contenido, $firma)) {
                return new self($contenido, $tipo, $extension, hash('sha256', $contenido));
            }
        }

        throw self::invalida();
    }

    public function tamanio(): int
    {
        return strlen($this->contenido);
    }

    /** RQ-INC-03: la clave depende del contenido; reenviar la misma foto no crea otro objeto. */
    public function claveEn(string $idIncidencia): string
    {
        return "incidencias/{$idIncidencia}/{$this->sha256}.{$this->extension}";
    }

    public static function invalida(): ExcepcionDominio
    {
        return ExcepcionDominio::reglaNegocio('FOTO_INVALIDA', 'La fotografía debe ser JPEG o PNG de hasta 10 MB.');
    }
}
