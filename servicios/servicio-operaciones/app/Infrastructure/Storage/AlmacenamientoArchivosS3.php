<?php

namespace App\Infrastructure\Storage;

use App\Application\Contracts\AlmacenamientoArchivos;
use App\Application\Contracts\UrlTemporal;
use Aws\S3\S3Client;
use DateTimeImmutable;
use DateTimeZone;

/**
 * Bucket privado de fotos (spec-incidencias.md 2.1). La firma de una URL incluye el host, por eso se firma con un
 * cliente aparte cuando el endpoint público difiere del interno (en local, `localhost:4566` frente a `localstack:4566`).
 */
final class AlmacenamientoArchivosS3 implements AlmacenamientoArchivos
{
    public function __construct(
        private readonly S3Client $interno,
        private readonly S3Client $publico,
        private readonly string $bucket,
    ) {}

    public function guardar(string $clave, string $contenido, string $tipoContenido): void
    {
        $this->interno->putObject([
            'Bucket' => $this->bucket,
            'Key' => $clave,
            'Body' => $contenido,
            'ContentType' => $tipoContenido,
        ]);
    }

    public function borrar(string $clave): void
    {
        $this->interno->deleteObject(['Bucket' => $this->bucket, 'Key' => $clave]);
    }

    public function urlTemporal(string $clave, int $minutos): UrlTemporal
    {
        $expiraEn = (new DateTimeImmutable('now', new DateTimeZone('UTC')))->modify("+{$minutos} minutes");
        $solicitud = $this->publico->createPresignedRequest(
            $this->publico->getCommand('GetObject', ['Bucket' => $this->bucket, 'Key' => $clave]),
            $expiraEn,
        );

        return new UrlTemporal((string) $solicitud->getUri(), $expiraEn);
    }
}
