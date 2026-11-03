<?php

namespace App\Application\UseCases\Saga;

use App\Application\Contracts\RegistroAuditoria;
use App\Domain\FieldTask\LaborAgricola;
use App\Domain\Saga\ConfiguracionSaga;
use App\Domain\Saga\PasoSaga;
use App\Domain\Saga\RepositorioSaga;
use App\Domain\Saga\Saga;
use App\Domain\Shared\Uuid;
use DateTimeImmutable;

/**
 * Inicia la Saga de una labor realizada con insumos (spec-saga.md RQ-SAG-01). Lo usan, dentro de su propia
 * unidad de trabajo, el registro, la realización y la revalidación de labores:
 *
 *   $saga = preparar($labor)            ← antes de guardar la labor (le asigna idSaga)
 *   registrar($saga)                    ← dentro de la unidad de trabajo, junto con la labor
 *   enviar($saga)                       ← después de confirmar
 */
final class IniciarSaga
{
    public const ACTOR = 'servicio-operaciones';

    public function __construct(
        private readonly RepositorioSaga $repositorio,
        private readonly RegistroAuditoria $auditoria,
        private readonly EnvioComandos $envio,
        private readonly ConfiguracionSaga $config,
    ) {}

    public function preparar(LaborAgricola $labor, DateTimeImmutable $ahora): ?Saga
    {
        if (! $labor->requiereSaga()) {
            return null;
        }
        $saga = Saga::iniciar(Uuid::v4(), $labor, $ahora, $this->config);
        $labor->iniciarSaga($saga->idSaga);

        return $saga;
    }

    public function registrar(?Saga $saga): void
    {
        if ($saga === null) {
            return;
        }
        $this->repositorio->guardarNueva($saga);
        $this->auditoria->registrar(self::ACTOR, 'INICIAR_SAGA', 'SAGA', $saga->idSaga);
    }

    public function enviar(?Saga $saga): void
    {
        if ($saga !== null) {
            $this->envio->enviar($saga, PasoSaga::DESCONTAR_INSUMOS);
        }
    }
}
