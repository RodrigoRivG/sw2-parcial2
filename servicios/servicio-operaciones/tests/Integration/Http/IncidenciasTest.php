<?php

use Tests\Support\DatosIncidencia;
use Tests\Support\DatosLabor;

beforeEach(function () {
    $this->parcela = DatosLabor::uuid();
    $this->tecnico = $this->encabezados(['tecnico_campo'], 'tec-ana');
    $this->gerente = $this->encabezados(['gerencia']);
});

describe('Historia 1 — registrar con fotografía', function () {
    it('guarda la foto en S3 con la clave por contenido, la incidencia sin URL pública y la auditoría (escenario 1)', function () {
        $campania = DatosLabor::uuid();
        $datos = DatosIncidencia::datos($this->parcela, ['idCampania' => $campania, 'descripcion' => '  Pulgón en el sector sur ']);
        $foto = DatosIncidencia::jpeg(3 * 1024 * 1024);

        $respuesta = DatosIncidencia::enviar($this, $datos, $foto, $this->tecnico)
            ->assertCreated()
            ->assertHeader('Location', url(DatosIncidencia::RUTA.'/'.$datos['idOperacion']))
            ->assertJson([
                'id' => $datos['idOperacion'],
                'tipo' => 'PLAGA',
                'descripcion' => 'Pulgón en el sector sur',
                'idParcela' => $this->parcela,
                'idCampania' => $campania,
                'foto' => ['tipoContenido' => 'image/jpeg', 'tamanio' => 3 * 1024 * 1024],
                'clasificacion' => null,
                'registradaPor' => ['id' => 'tec-ana', 'nombre' => 'Usuario tec-ana'],
                'fechaObservacion' => $datos['fechaObservacion'],
            ]);

        $clave = 'incidencias/'.$datos['idOperacion'].'/'.hash('sha256', $foto).'.jpg';
        $objeto = DatosIncidencia::s3()->headObject(['Bucket' => config('aws.s3.bucket'), 'Key' => $clave]);
        expect($objeto['ContentType'])->toBe('image/jpeg')
            ->and((int) $objeto['ContentLength'])->toBe(3 * 1024 * 1024)
            ->and($respuesta->json('foto.url'))->toContain($clave)->toContain('X-Amz-Signature=')
            ->and(DatosIncidencia::auditorias($datos['idOperacion']))->toBe(['REGISTRAR_INCIDENCIA']);
    });

    it('acepta una incidencia sin campaña y una foto PNG (escenarios 2 y 3)', function () {
        $datos = DatosIncidencia::datos($this->parcela, ['tipo' => 'DANIO']);

        DatosIncidencia::enviar($this, $datos, DatosIncidencia::png(), $this->tecnico, 'foto.png')
            ->assertCreated()
            ->assertJson(['idCampania' => null, 'tipo' => 'DANIO', 'foto' => ['tipoContenido' => 'image/png']]);
        expect(DatosIncidencia::objetosDe($datos['idOperacion'])[0])->toEndWith('.png');
    });

    it('identifica el formato por el contenido, no por la extensión', function () {
        $datos = DatosIncidencia::datos($this->parcela);

        DatosIncidencia::enviar($this, $datos, DatosIncidencia::jpeg(), $this->tecnico, 'foto.png')
            ->assertCreated()->assertJson(['foto' => ['tipoContenido' => 'image/jpeg']]);
    });

    it('rechaza GIF, PDF renombrado, 0 bytes y más de 10 MB con 422 FOTO_INVALIDA, sin guardar nada (escenario 4)', function (Closure $foto) {
        $datos = DatosIncidencia::datos($this->parcela);

        DatosIncidencia::enviar($this, $datos, $foto(), $this->tecnico)->assertStatus(422)->assertJson(['codigo' => 'FOTO_INVALIDA']);

        $this->getJson(DatosIncidencia::RUTA.'/'.$datos['idOperacion'], $this->gerente)->assertNotFound();
        expect(DatosIncidencia::objetosDe($datos['idOperacion']))->toBe([]);
    })->with([
        'GIF' => fn () => 'GIF89a'.random_bytes(100),
        'PDF con extensión .jpg' => fn () => "%PDF-1.7\n".random_bytes(100),
        '0 bytes' => fn () => '',
        '10 MB + 1 byte' => fn () => DatosIncidencia::jpeg(10 * 1024 * 1024 + 1),
    ]);

    it('acepta exactamente 10 MB', function () {
        DatosIncidencia::enviar($this, DatosIncidencia::datos($this->parcela), DatosIncidencia::jpeg(10 * 1024 * 1024), $this->tecnico)->assertCreated();
    });

    it('sin foto o con datos inválidos responde 400 (escenario 5 y casos borde)', function (Closure $partes) {
        $this->post(DatosIncidencia::RUTA, $partes($this->parcela), $this->tecnico)
            ->assertStatus(400)->assertJson(['codigo' => 'DATOS_INVALIDOS']);
    })->with([
        'sin foto' => fn ($p) => ['datos' => json_encode(DatosIncidencia::datos($p))],
        'foto como texto' => fn ($p) => ['datos' => json_encode(DatosIncidencia::datos($p)), 'foto' => 'abc'],
        'sin datos' => fn ($p) => ['foto' => DatosIncidencia::archivo(DatosIncidencia::jpeg())],
        'datos que no es JSON' => fn ($p) => ['datos' => '{"tipo": ', 'foto' => DatosIncidencia::archivo(DatosIncidencia::jpeg())],
        'tipo desconocido' => fn ($p) => ['datos' => json_encode(DatosIncidencia::datos($p, ['tipo' => 'HELADA'])), 'foto' => DatosIncidencia::archivo(DatosIncidencia::jpeg())],
        'descripción de 1001' => fn ($p) => ['datos' => json_encode(DatosIncidencia::datos($p, ['descripcion' => str_repeat('a', 1001)])), 'foto' => DatosIncidencia::archivo(DatosIncidencia::jpeg())],
        'descripción en blanco' => fn ($p) => ['datos' => json_encode(DatosIncidencia::datos($p, ['descripcion' => '   '])), 'foto' => DatosIncidencia::archivo(DatosIncidencia::jpeg())],
        'campo no permitido en datos' => fn ($p) => ['datos' => json_encode(DatosIncidencia::datos($p, ['prioridad' => 'ALTA'])), 'foto' => DatosIncidencia::archivo(DatosIncidencia::jpeg())],
        'parte no permitida' => fn ($p) => ['datos' => json_encode(DatosIncidencia::datos($p)), 'foto' => DatosIncidencia::archivo(DatosIncidencia::jpeg()), 'extra' => 'x'],
        'idParcela que no es UUID' => fn ($p) => ['datos' => json_encode(DatosIncidencia::datos($p, ['idParcela' => 'P1'])), 'foto' => DatosIncidencia::archivo(DatosIncidencia::jpeg())],
    ]);

    it('rechaza una observación en el futuro con 422 FECHA_OBSERVACION_INVALIDA (escenario 6)', function () {
        DatosIncidencia::enviar($this, DatosIncidencia::datos($this->parcela, ['fechaObservacion' => DatosLabor::fecha('+10 minutes')]), DatosIncidencia::jpeg(), $this->tecnico)
            ->assertStatus(422)->assertJson(['codigo' => 'FECHA_OBSERVACION_INVALIDA']);
    });

    it('solo un técnico de campo registra (escenario 7)', function (string $rol) {
        DatosIncidencia::enviar($this, DatosIncidencia::datos($this->parcela), DatosIncidencia::jpeg(), $this->encabezados([$rol]))
            ->assertForbidden()->assertJson(['codigo' => 'SIN_PERMISO']);
    })->with(['administrador', 'gerencia', 'lectura_operaciones']);
});

describe('Historia 2 — clasificación de la foto', function () {
    it('guarda la clasificación y la devuelve como orientativa', function () {
        $datos = DatosIncidencia::datos($this->parcela, ['clasificacion' => [
            'categoria' => 'roya', 'confianza' => '0.8731', 'versionModelo' => 'clasificador-1.2.0', 'origen' => 'DISPOSITIVO',
        ]]);

        DatosIncidencia::enviar($this, $datos, DatosIncidencia::jpeg(), $this->tecnico)->assertCreated();

        $this->getJson(DatosIncidencia::RUTA.'/'.$datos['idOperacion'], $this->gerente)->assertOk()->assertJson(['clasificacion' => [
            'categoria' => 'roya', 'confianza' => '0.8731', 'versionModelo' => 'clasificador-1.2.0', 'origen' => 'DISPOSITIVO', 'orientativa' => true,
        ]]);
    });

    it('confianza fuera de 0 a 1 es 422; como número JSON o con 5 decimales es 400', function (mixed $confianza, int $estado) {
        $datos = DatosIncidencia::datos($this->parcela, ['clasificacion' => [
            'categoria' => 'roya', 'confianza' => $confianza, 'versionModelo' => 'v1', 'origen' => 'SERVIDOR',
        ]]);

        DatosIncidencia::enviar($this, $datos, DatosIncidencia::jpeg(), $this->tecnico)->assertStatus($estado);
    })->with([
        ['1.2', 422], ['-0.1', 422], [0.87, 400], ['0.87315', 400], ['0', 201], ['1', 201],
    ]);
});

describe('Historia 5 — consultar', function () {
    it('lista por parcela y tipo, más recientes primero, con URL descargable que vence (escenarios 1 y 2)', function () {
        $fotos = [];
        foreach ([['PLAGA', '-3 hours'], ['ENFERMEDAD', '-2 hours'], ['PLAGA', '-1 hours']] as [$tipo, $cuando]) {
            $datos = DatosIncidencia::datos($this->parcela, ['tipo' => $tipo, 'fechaObservacion' => DatosLabor::fecha($cuando)]);
            $fotos[$datos['idOperacion']] = DatosIncidencia::jpeg();
            DatosIncidencia::enviar($this, $datos, $fotos[$datos['idOperacion']], $this->tecnico)->assertCreated();
        }

        $pagina = $this->getJson(DatosIncidencia::RUTA."?idParcela={$this->parcela}&tipo=PLAGA", $this->gerente)->assertOk();

        $items = $pagina->json('items');
        expect(array_column($items, 'tipo'))->toBe(['PLAGA', 'PLAGA'])
            ->and($items[0]['fechaObservacion'] > $items[1]['fechaObservacion'])->toBeTrue()
            ->and(file_get_contents($items[0]['foto']['url']))->toBe($fotos[$items[0]['id']]);
        $expira = new DateTimeImmutable($items[0]['foto']['expiraEn']);
        expect($expira->getTimestamp() - time())->toBeGreaterThan(9 * 60)->toBeLessThanOrEqual(10 * 60);

        // Firma con 1 s de vigencia: después de vencer, S3 responde 403
        $url = (string) DatosIncidencia::s3()->createPresignedRequest(
            DatosIncidencia::s3()->getCommand('GetObject', ['Bucket' => config('aws.s3.bucket'), 'Key' => DatosIncidencia::objetosDe($items[0]['id'])[0]]), '+1 second')->getUri();
        sleep(2);
        expect(@file_get_contents($url))->toBeFalse()->and($http_response_header[0] ?? '')->toContain('403');
    });

    it('un técnico ve solo las suyas (escenario 3)', function () {
        $mia = DatosIncidencia::datos($this->parcela);
        $ajena = DatosIncidencia::datos($this->parcela);
        DatosIncidencia::enviar($this, $mia, DatosIncidencia::jpeg(), $this->tecnico)->assertCreated();
        DatosIncidencia::enviar($this, $ajena, DatosIncidencia::jpeg(), $this->encabezados(['tecnico_campo'], 'tec-otro'))->assertCreated();

        $mias = $this->getJson(DatosIncidencia::RUTA."?mias=true&idParcela={$this->parcela}", $this->tecnico)->assertOk();

        expect(array_column($mias->json('items'), 'id'))->toBe([$mia['idOperacion']]);
        $this->getJson(DatosIncidencia::RUTA."?idParcela={$this->parcela}", $this->tecnico)->assertForbidden();
        $this->getJson(DatosIncidencia::RUTA."/{$ajena['idOperacion']}", $this->tecnico)->assertForbidden();
        $this->getJson(DatosIncidencia::RUTA."/{$mia['idOperacion']}", $this->tecnico)->assertOk();
    });

    it('lista por campaña con lectura_operaciones y pagina por cursor', function () {
        $campania = DatosLabor::uuid();
        foreach (range(1, 3) as $i) {
            DatosIncidencia::enviar($this, DatosIncidencia::datos($this->parcela, ['idCampania' => $campania, 'fechaObservacion' => DatosLabor::fecha("-{$i} hours")]), DatosIncidencia::jpeg(), $this->tecnico)->assertCreated();
        }
        $ia = $this->encabezados(['lectura_operaciones'], 'service-account-ia');

        $primera = $this->getJson(DatosIncidencia::RUTA."?idCampania={$campania}&limite=2", $ia)->assertOk();
        $segunda = $this->getJson(DatosIncidencia::RUTA."?idCampania={$campania}&limite=2&cursor=".$primera->json('siguienteCursor'), $ia)->assertOk();

        expect(count($primera->json('items')) + count($segunda->json('items')))->toBe(3);
    });

    it('400 sin filtro principal, 404 si no existe (escenarios 4 y 5)', function () {
        $this->getJson(DatosIncidencia::RUTA.'?tipo=PLAGA', $this->gerente)->assertStatus(400)->assertJson(['codigo' => 'DATOS_INVALIDOS']);
        $this->getJson(DatosIncidencia::RUTA.'/'.DatosLabor::uuid(), $this->gerente)->assertNotFound()->assertJson(['codigo' => 'INCIDENCIA_NO_ENCONTRADA']);
    });
});
