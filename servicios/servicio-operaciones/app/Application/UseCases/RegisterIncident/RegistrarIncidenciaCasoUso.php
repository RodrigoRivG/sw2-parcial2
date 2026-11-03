<?php

namespace App\Application\UseCases\RegisterIncident;

use App\Application\Contracts\AlmacenamientoArchivos;
use App\Application\Contracts\ConflictoEscritura;
use App\Application\Contracts\RegistroAuditoria;
use App\Application\Contracts\Reloj;
use App\Application\Contracts\UnidadTrabajo;
use App\Application\Security\SinPermiso;
use App\Application\Security\UsuarioAutenticado;
use App\Domain\FieldTask\Responsable;
use App\Domain\Incident\ClasificacionImagen;
use App\Domain\Incident\FotoIncidencia;
use App\Domain\Incident\Incidencia;
use App\Domain\Incident\ReferenciaFoto;
use App\Domain\Incident\RepositorioIncidencia;
use App\Domain\Shared\ExcepcionDominio;
use App\Domain\Shared\Huella;
use Psr\Log\LoggerInterface;
use Throwable;

/**
 * Registra una incidencia con su foto (spec-incidencias.md 2.4): S3 → DynamoDB → evento para n8n.
 */
final class RegistrarIncidenciaCasoUso
{
    public function __construct(
        private readonly RepositorioIncidencia $repositorio,
        private readonly AlmacenamientoArchivos $almacenamiento,
        private readonly UnidadTrabajo $unidadTrabajo,
        private readonly RegistroAuditoria $auditoria,
        private readonly NotificacionIncidencia $notificacion,
        private readonly Reloj $reloj,
        private readonly LoggerInterface $log,
    ) {}

    public function ejecutar(RegistrarIncidenciaEntrada $entrada, UsuarioAutenticado $usuario): ResultadoIncidencia
    {
        if (! $usuario->tieneRol('tecnico_campo')) {
            throw new SinPermiso('Solo un técnico de campo registra incidencias.');
        }

        // 1. Foto y clasificación (422) antes de tocar nada
        $foto = FotoIncidencia::desdeContenido($entrada->contenidoFoto);
        $clasificacion = $entrada->clasificacion === null ? null : ClasificacionImagen::crear(
            $entrada->clasificacion['categoria'],
            $entrada->clasificacion['confianza'],
            $entrada->clasificacion['versionModelo'],
            $entrada->clasificacion['origen'],
        );
        $id = strtolower($entrada->idOperacion);
        $idCampania = $entrada->idCampania === null ? null : strtolower($entrada->idCampania);

        // 2. Huella con el contenido de la foto (RQ-INC-05)
        $huella = Huella::calcular([
            'operacion' => 'REGISTRAR_INCIDENCIA',
            'idOperacion' => $id,
            'fechaCreacion' => $entrada->fechaCreacion->format('Y-m-d\TH:i:s\Z'),
            'tipo' => $entrada->tipo->value,
            'descripcion' => $entrada->descripcion,
            'fechaObservacion' => $entrada->fechaObservacion->format('Y-m-d\TH:i:s\Z'),
            'idParcela' => strtolower($entrada->idParcela),
            'idCampania' => $idCampania,
            'clasificacion' => $clasificacion === null ? null : [
                $clasificacion->categoria, $clasificacion->confianza, $clasificacion->versionModelo, $clasificacion->origen->value,
            ],
            'foto' => $foto->sha256,
        ], $usuario->id);

        // 3. Repetición: no se sube la foto ni se audita ni se publica
        $existente = $this->repositorio->buscar($id);
        if ($existente !== null) {
            return $this->repeticion($existente, $huella);
        }

        $ahora = $this->reloj->ahora();
        $clave = $foto->claveEn($id);
        $incidencia = Incidencia::registrar($id, $huella, $entrada->tipo, $entrada->descripcion, $entrada->fechaObservacion,
            $entrada->fechaCreacion, strtolower($entrada->idParcela), $idCampania,
            new ReferenciaFoto($clave, $foto->tipoContenido, $foto->tamanio()), $clasificacion,
            new Responsable($usuario->id, $usuario->nombre), $ahora);

        // 4. S3, y 5. DynamoDB con la auditoría
        $this->almacenamiento->guardar($clave, $foto->contenido, $foto->tipoContenido);
        try {
            $this->unidadTrabajo->ejecutar(function () use ($incidencia, $usuario) {
                $this->repositorio->guardarNueva($incidencia);
                $this->auditoria->registrar($usuario->id, 'REGISTRAR_INCIDENCIA', 'INCIDENCIA', $incidencia->id);
            });
        } catch (ConflictoEscritura) {
            $ganadora = $this->repositorio->buscar($id) ?? throw new \LogicException('La incidencia que ganó la carrera no existe.');
            if ($ganadora->foto->clave !== $clave) {
                $this->borrarSinFallar($clave);
            }

            return $this->repeticion($ganadora, $huella);
        } catch (Throwable $e) {
            $this->borrarSinFallar($clave);
            throw $e;
        }

        // 6. Evento para n8n
        $this->notificacion->notificar($incidencia, $entrada->idCorrelacion);

        return new ResultadoIncidencia($incidencia, false);
    }

    private function repeticion(Incidencia $existente, string $huella): ResultadoIncidencia
    {
        if (! hash_equals($existente->huella, $huella)) {
            throw ExcepcionDominio::conflicto('CONFLICTO_IDEMPOTENCIA', 'La operación ya se procesó con otro contenido.');
        }

        return new ResultadoIncidencia($existente, true);
    }

    /** Mejor esfuerzo: un objeto huérfano bajo incidencias/{id}/ no lo referencia nadie (spec-incidencias.md, casos borde). */
    private function borrarSinFallar(string $clave): void
    {
        try {
            $this->almacenamiento->borrar($clave);
        } catch (Throwable $e) {
            $this->log->warning('No se pudo borrar la foto huérfana', ['clave' => $clave, 'error' => $e->getMessage()]);
        }
    }
}
