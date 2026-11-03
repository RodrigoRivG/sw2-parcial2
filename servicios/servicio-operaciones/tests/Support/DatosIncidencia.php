<?php

namespace Tests\Support;

use App\Infrastructure\Persistence\DynamoDb\NombresTablas;
use Aws\DynamoDb\DynamoDbClient;
use Aws\S3\S3Client;
use Illuminate\Http\UploadedFile;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

/**
 * Incidencias de prueba (spec-incidencias.md 2.2): la parte `datos` y fotos con la firma de JPEG o PNG.
 */
final class DatosIncidencia
{
    public const RUTA = '/api/operaciones/v1/incidencias';

    /** @return array<string, mixed> */
    public static function datos(string $idParcela, array $cambios = []): array
    {
        return array_merge([
            'idOperacion' => DatosLabor::uuid(),
            'fechaCreacion' => DatosLabor::fecha('-1 minute'),
            'tipo' => 'PLAGA',
            'descripcion' => 'Manchas anaranjadas en hojas del borde norte',
            'fechaObservacion' => DatosLabor::fecha('-10 minutes'),
            'idParcela' => $idParcela,
        ], $cambios);
    }

    /** Bytes que empiezan con la firma de JPEG; el resto, aleatorio, para que cada foto sea distinta. */
    public static function jpeg(int $bytes = 2048): string
    {
        return "\xFF\xD8\xFF\xE0".random_bytes(max(0, $bytes - 4));
    }

    public static function png(int $bytes = 2048): string
    {
        return "\x89PNG\r\n\x1A\n".random_bytes(max(0, $bytes - 8));
    }

    public static function archivo(string $contenido, string $nombre = 'foto.jpg'): UploadedFile
    {
        return UploadedFile::fake()->createWithContent($nombre, $contenido);
    }

    /**
     * @param  array<string, mixed>  $datos
     * @param  array<string, string>  $encabezados
     */
    public static function enviar(TestCase $test, array $datos, ?string $foto, array $encabezados, string $nombreArchivo = 'foto.jpg'): TestResponse
    {
        $partes = ['datos' => json_encode($datos)];
        if ($foto !== null) {
            $partes['foto'] = self::archivo($foto, $nombreArchivo);
        }

        return $test->post(self::RUTA, $partes, $encabezados);
    }

    public static function s3(): S3Client
    {
        return new S3Client([
            'region' => 'us-east-1',
            'version' => '2006-03-01',
            'endpoint' => (string) config('aws.s3.endpoint'),
            'use_path_style_endpoint' => true,
            'credentials' => ['key' => config('aws.clave'), 'secret' => config('aws.secreto')],
        ]);
    }

    /** @return list<string> claves de S3 bajo incidencias/{id}/ */
    public static function objetosDe(string $idIncidencia): array
    {
        $resultado = self::s3()->listObjectsV2(['Bucket' => config('aws.s3.bucket'), 'Prefix' => "incidencias/{$idIncidencia}/"]);

        return array_column($resultado['Contents'] ?? [], 'Key');
    }

    /** @return list<string> */
    public static function auditorias(string $idIncidencia): array
    {
        $resultado = app(DynamoDbClient::class)->query([
            'TableName' => app(NombresTablas::class)->de('registros_auditoria'),
            'IndexName' => 'gsi_entidad',
            'KeyConditionExpression' => 'entidad_id = :e',
            'ExpressionAttributeValues' => [':e' => ['S' => "INCIDENCIA#{$idIncidencia}"]],
        ]);

        return array_map(fn ($item) => $item['accion']['S'], $resultado['Items']);
    }
}
