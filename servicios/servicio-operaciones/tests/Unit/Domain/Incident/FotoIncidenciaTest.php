<?php

use App\Domain\Incident\FotoIncidencia;
use App\Domain\Shared\ExcepcionDominio;

it('reconoce JPEG y PNG por su firma, con su tipo, extensión y clave por contenido', function () {
    $jpeg = "\xFF\xD8\xFF\xE0datos";
    $png = "\x89PNG\r\n\x1A\ndatos";

    $fotoJpeg = FotoIncidencia::desdeContenido($jpeg);
    $fotoPng = FotoIncidencia::desdeContenido($png);

    expect([$fotoJpeg->tipoContenido, $fotoJpeg->extension, $fotoJpeg->tamanio()])->toBe(['image/jpeg', 'jpg', 9])
        ->and([$fotoPng->tipoContenido, $fotoPng->extension])->toBe(['image/png', 'png'])
        ->and($fotoJpeg->claveEn('i1'))->toBe('incidencias/i1/'.hash('sha256', $jpeg).'.jpg');
});

it('acepta exactamente 10 MB', function () {
    expect(FotoIncidencia::desdeContenido("\xFF\xD8\xFF".str_repeat('a', FotoIncidencia::TAMANIO_MAXIMO - 3))->tamanio())
        ->toBe(10 * 1024 * 1024);
});

it('rechaza con FOTO_INVALIDA lo que no es JPEG ni PNG, 0 bytes y más de 10 MB', function (string $contenido) {
    expect(fn () => FotoIncidencia::desdeContenido($contenido))
        ->toThrow(fn (ExcepcionDominio $e) => expect($e->codigo)->toBe('FOTO_INVALIDA'));
})->with([
    'GIF' => ['GIF89a....'],
    'PDF' => ["%PDF-1.7\n"],
    'vacío' => [''],
    'JPEG truncado' => ["\xFF\xD8"],
    'PNG sin firma completa' => ["\x89PNG"],
    '10 MB + 1' => ["\xFF\xD8\xFF".str_repeat('a', 10 * 1024 * 1024 - 2)],
]);
