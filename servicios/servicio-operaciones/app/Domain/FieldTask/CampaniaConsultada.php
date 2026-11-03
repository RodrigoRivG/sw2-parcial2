<?php

namespace App\Domain\FieldTask;

use App\Domain\Shared\Motivo;

/**
 * Lo que este servicio necesita del estado de una campaña de servicio-gestion (spec-labores.md AC-01).
 */
final class CampaniaConsultada
{
    public function __construct(
        public readonly string $id,
        public readonly string $idParcela,
        public readonly string $estado,
    ) {}

    /**
     * Motivo por el que no se puede registrar una labor de esa parcela en esta campaña (RN-06), o null si se puede.
     */
    public function rechazoPara(string $idParcela): ?Motivo
    {
        if ($this->estado === 'FINALIZADA') {
            return new Motivo('CAMPANIA_FINALIZADA', 'No se pueden registrar labores en una campaña finalizada.');
        }
        if ($this->idParcela !== $idParcela) {
            return new Motivo('PARCELA_NO_CORRESPONDE', 'La campaña no pertenece a la parcela indicada.');
        }

        return null;
    }

    public static function noEncontrada(): Motivo
    {
        return new Motivo('CAMPANIA_NO_ENCONTRADA', 'La campaña no existe.');
    }
}
