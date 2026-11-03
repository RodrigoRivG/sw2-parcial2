<?php

namespace App\Application\UseCases\SyncOfflineOperations;

use App\Application\Contracts\CampaniaNoDisponible;
use App\Application\Contracts\PasarelaCampania;
use App\Domain\FieldTask\CampaniaConsultada;

/**
 * Consulta cada campaña una sola vez mientras se procesa un lote, también cuando gestión no responde
 * (spec-sincronizacion.md RQ-SIN-07). Fuera de un lote no guarda nada: cada solicitud consulta a gestión.
 */
final class PasarelaCampaniaConCache implements PasarelaCampania
{
    private bool $activa = false;

    /** @var array<string, CampaniaConsultada|CampaniaNoDisponible|null> */
    private array $respuestas = [];

    public function __construct(private readonly PasarelaCampania $pasarela) {}

    public function activar(): void
    {
        $this->activa = true;
        $this->respuestas = [];
    }

    public function desactivar(): void
    {
        $this->activa = false;
        $this->respuestas = [];
    }

    public function consultar(string $idCampania): ?CampaniaConsultada
    {
        if (! $this->activa) {
            return $this->pasarela->consultar($idCampania);
        }

        if (! array_key_exists($idCampania, $this->respuestas)) {
            try {
                $this->respuestas[$idCampania] = $this->pasarela->consultar($idCampania);
            } catch (CampaniaNoDisponible $e) {
                $this->respuestas[$idCampania] = $e;
            }
        }

        $respuesta = $this->respuestas[$idCampania];
        if ($respuesta instanceof CampaniaNoDisponible) {
            throw $respuesta;
        }

        return $respuesta;
    }
}
