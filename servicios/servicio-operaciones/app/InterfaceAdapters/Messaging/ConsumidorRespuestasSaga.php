<?php

namespace App\InterfaceAdapters\Messaging;

use App\Application\UseCases\Saga\ProcesarRespuestaSaga;
use App\Application\UseCases\Saga\RespuestaInvalida;
use App\Domain\Saga\TipoRespuesta;
use Illuminate\Support\Facades\Context;
use Psr\Log\LoggerInterface;
use Throwable;

/**
 * Procesa una respuesta de `servicio-operaciones.respuestas-saga` (spec-saga.md 2.4):
 * sobre inválido o respuesta no procesable → DLQ sin reintentos; fallo técnico → 3 reintentos y luego DLQ.
 */
final class ConsumidorRespuestasSaga
{
    /**
     * @param  list<int>  $esperasMs  espera antes de cada reintento (README D-14)
     */
    public function __construct(
        private readonly ProcesarRespuestaSaga $procesar,
        private readonly LoggerInterface $log,
        private readonly array $esperasMs = [1000, 2000, 4000],
    ) {}

    /**
     * @return string|null null para confirmar; el motivo para enviarlo a la DLQ
     */
    public function manejar(string $cuerpo): ?string
    {
        $sobre = SobreMensaje::interpretar($cuerpo);
        if (is_string($sobre)) {
            return $this->aDlq($sobre, null);
        }
        Context::add('idCorrelacion', $sobre->idCorrelacion);

        $tipo = TipoRespuesta::tryFrom($sobre->tipo);
        if ($tipo === null) {
            return $this->aDlq("Tipo de mensaje desconocido: {$sobre->tipo}.", $sobre);
        }
        if ($sobre->version !== 1) {
            return $this->aDlq('Versión de mensaje no soportada.', $sobre);
        }

        for ($intento = 0; ; $intento++) {
            try {
                $decision = $this->procesar->ejecutar($tipo, $sobre->idMensaje, $sobre->idCorrelacion, $sobre->datos);
                $this->log->info('Respuesta de la Saga procesada', [
                    'idCorrelacion' => $sobre->idCorrelacion,
                    'idMensaje' => $sobre->idMensaje,
                    'tipo' => $sobre->tipo,
                    'resultado' => $decision->tardia ? 'TARDIA' : 'APLICADA',
                ]);

                return null;
            } catch (RespuestaInvalida $e) {
                return $this->aDlq($e->getMessage(), $sobre);
            } catch (Throwable $e) {
                if ($intento >= count($this->esperasMs)) {
                    return $this->aDlq('Fallo técnico tras '.($intento + 1).' intentos: '.$e->getMessage(), $sobre);
                }
                $this->log->warning('Fallo técnico al procesar la respuesta; se reintenta', [
                    'idCorrelacion' => $sobre->idCorrelacion,
                    'idMensaje' => $sobre->idMensaje,
                    'intento' => $intento + 1,
                    'error' => $e->getMessage(),
                ]);
                usleep($this->esperasMs[$intento] * 1000);
            }
        }
    }

    private function aDlq(string $motivo, ?SobreMensaje $sobre): string
    {
        $this->log->error('Respuesta de la Saga enviada a la DLQ', [
            'idCorrelacion' => $sobre?->idCorrelacion,
            'idMensaje' => $sobre?->idMensaje,
            'tipo' => $sobre?->tipo,
            'motivo' => $motivo,
        ]);

        return $motivo;
    }
}
