<?php

namespace App\Application\UseCases\Saga;

use App\Domain\Saga\RepositorioSaga;
use App\Domain\Saga\Saga;
use App\Domain\Shared\ExcepcionDominio;

final class ConsultarSagaCasoUso
{
    public function __construct(private readonly RepositorioSaga $sagas) {}

    public function ejecutar(string $idSaga): Saga
    {
        return $this->sagas->buscar(strtolower($idSaga))
            ?? throw ExcepcionDominio::noEncontrado('SAGA_NO_ENCONTRADA', 'La Saga no existe.');
    }
}
