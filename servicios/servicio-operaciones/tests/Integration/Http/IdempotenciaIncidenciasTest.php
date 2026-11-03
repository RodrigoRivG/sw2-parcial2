<?php

use App\Application\Security\UsuarioAutenticado;
use App\Application\UseCases\RegisterIncident\RegistrarIncidenciaCasoUso;
use App\Application\UseCases\RegisterIncident\RegistrarIncidenciaEntrada;
use App\Domain\Incident\TipoIncidencia;
use Illuminate\Foundation\Application;
use Tests\Support\DatosIncidencia;
use Tests\Support\DatosLabor;
use Tests\Support\EnParalelo;

beforeEach(function () {
    $this->parcela = DatosLabor::uuid();
    $this->tecnico = $this->encabezados(['tecnico_campo'], 'tec-ana');
});

it('una repetición con los mismos datos y la misma foto responde 200 sin subir otra foto, auditar ni publicar (escenario 1)', function () {
    $datos = DatosIncidencia::datos($this->parcela);
    $foto = DatosIncidencia::jpeg();

    DatosIncidencia::enviar($this, $datos, $foto, $this->tecnico)->assertCreated();
    DatosIncidencia::enviar($this, $datos, $foto, $this->tecnico)->assertOk()->assertJson(['id' => $datos['idOperacion']]);

    expect(DatosIncidencia::objetosDe($datos['idOperacion']))->toHaveCount(1)
        ->and(DatosIncidencia::auditorias($datos['idOperacion']))->toBe(['REGISTRAR_INCIDENCIA']);
});

it('con otra descripción u otra foto responde 409; la foto original no cambia y la nueva no queda en S3 (escenario 2)', function (Closure $cambiar) {
    $datos = DatosIncidencia::datos($this->parcela);
    $foto = DatosIncidencia::jpeg();
    DatosIncidencia::enviar($this, $datos, $foto, $this->tecnico)->assertCreated();
    [$otrosDatos, $otraFoto] = $cambiar($datos, $foto);

    DatosIncidencia::enviar($this, $otrosDatos, $otraFoto, $this->tecnico)->assertStatus(409)->assertJson(['codigo' => 'CONFLICTO_IDEMPOTENCIA']);

    expect(DatosIncidencia::objetosDe($datos['idOperacion']))->toBe(['incidencias/'.$datos['idOperacion'].'/'.hash('sha256', $foto).'.jpg']);
})->with([
    'otra descripción' => fn (array $d, string $f) => [[...$d, 'descripcion' => 'Otra cosa'], $f],
    'otra foto' => fn (array $d, string $f) => [$d, DatosIncidencia::jpeg()],
]);

it('dos envíos simultáneos de la misma incidencia dejan una sola incidencia y un solo objeto en S3 (escenario 3)', function () {
    $idOperacion = DatosLabor::uuid();
    $foto = DatosIncidencia::jpeg(50_000);
    $parcela = $this->parcela;
    $utc = new DateTimeZone('UTC');
    $creacion = new DateTimeImmutable(DatosLabor::fecha('-1 minute'), $utc);

    $resultados = EnParalelo::ejecutar(5, function (Application $app) use ($idOperacion, $foto, $parcela, $creacion) {
        $resultado = $app->make(RegistrarIncidenciaCasoUso::class)->ejecutar(
            new RegistrarIncidenciaEntrada($idOperacion, $creacion, TipoIncidencia::PLAGA, 'Pulgón', $creacion, $parcela, null, null, $foto, 'corr'),
            new UsuarioAutenticado('tec-ana', 'Ana', ['tecnico_campo']),
        );

        return $resultado->repetida ? 'repetida' : 'nueva';
    });

    $conteo = array_count_values(array_map(fn (array $r) => $r['valor'] ?? $r['error'], $resultados));
    ksort($conteo);
    expect($conteo)->toBe(['nueva' => 1, 'repetida' => 4])
        ->and(DatosIncidencia::objetosDe($idOperacion))->toHaveCount(1)
        ->and(DatosIncidencia::auditorias($idOperacion))->toBe(['REGISTRAR_INCIDENCIA']);
});
