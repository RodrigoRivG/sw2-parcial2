<?php

namespace App\Application\UseCases\RegisterFieldTask;

use App\Application\Contracts\CampaniaNoDisponible;
use App\Application\Contracts\PasarelaCampania;
use App\Domain\FieldTask\CampaniaConsultada;
use App\Domain\FieldTask\ValidacionCampania;
use App\Domain\Shared\ExcepcionDominio;
use Psr\Log\LoggerInterface;

/**
 * Valida contra servicio-gestion que la campaña exista, no esté finalizada y sea de la parcela (RN-06).
 */
final class VerificadorCampania
{
    public function __construct(
        private readonly PasarelaCampania $pasarela,
        private readonly LoggerInterface $log,
    ) {}

    public function verificar(string $idCampania, string $idParcela): ResultadoVerificacion
    {
        try {
            $campania = $this->pasarela->consultar($idCampania);
        } catch (CampaniaNoDisponible $e) {
            $this->log->warning('servicio-gestion no respondió la consulta de campaña: la validación se difiere', [
                'idCampania' => $idCampania,
                'error' => $e->getMessage(),
            ]);

            return ResultadoVerificacion::noDisponible();
        }

        if ($campania === null) {
            return ResultadoVerificacion::rechazada(CampaniaConsultada::noEncontrada());
        }
        $rechazo = $campania->rechazoPara($idParcela);

        return $rechazo === null ? ResultadoVerificacion::valida() : ResultadoVerificacion::rechazada($rechazo);
    }

    /**
     * Para una solicitud: un rechazo se responde en el momento (RQ-LAB-13); si gestión no responde, la validación se difiere.
     */
    public function exigir(string $idCampania, string $idParcela): ValidacionCampania
    {
        $resultado = $this->verificar($idCampania, $idParcela);
        if (! $resultado->disponible) {
            return ValidacionCampania::PENDIENTE;
        }
        if ($resultado->rechazo !== null) {
            throw $resultado->rechazo->codigo === 'CAMPANIA_NO_ENCONTRADA'
                ? ExcepcionDominio::noEncontrado($resultado->rechazo->codigo, $resultado->rechazo->mensaje)
                : $resultado->rechazo->comoRegla();
        }

        return ValidacionCampania::VALIDADA;
    }
}
