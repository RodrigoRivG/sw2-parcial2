<?php

namespace App\Infrastructure\Persistence\DynamoDb;

use App\Application\Contracts\ConflictoEscritura;
use App\Application\Contracts\UnidadTrabajo;
use Aws\DynamoDb\DynamoDbClient;
use Aws\DynamoDb\Exception\DynamoDbException;

/**
 * Junta las escrituras de los repositorios y las envía en un solo TransactWriteItems (README D-08).
 * Fuera de `ejecutar`, cada escritura se envía sola, con la misma traducción de errores.
 */
final class UnidadTrabajoDynamo implements UnidadTrabajo
{
    /** @var list<array{0: array<string, mixed>, 1: string}>|null */
    private ?array $pendientes = null;

    public function __construct(private readonly DynamoDbClient $cliente) {}

    public function ejecutar(callable $operacion): mixed
    {
        if ($this->pendientes !== null) {
            return $operacion();
        }

        $this->pendientes = [];
        try {
            $resultado = $operacion();
            $escrituras = $this->pendientes;
        } finally {
            $this->pendientes = null;
        }

        $this->confirmar($escrituras);

        return $resultado;
    }

    /**
     * @param  array<string, mixed>  $escritura  un elemento de TransactItems (`Put`, `Update`, `Delete` o `ConditionCheck`)
     */
    public function agregar(array $escritura, string $etiqueta): void
    {
        if ($this->pendientes === null) {
            $this->confirmar([[$escritura, $etiqueta]]);

            return;
        }

        $this->pendientes[] = [$escritura, $etiqueta];
    }

    /**
     * @param  list<array{0: array<string, mixed>, 1: string}>  $escrituras
     */
    private function confirmar(array $escrituras): void
    {
        if ($escrituras === []) {
            return;
        }

        try {
            $this->cliente->transactWriteItems(['TransactItems' => array_column($escrituras, 0)]);
        } catch (DynamoDbException $e) {
            if ($e->getAwsErrorCode() === 'TransactionCanceledException') {
                $indice = $this->indiceCondicionFallida($e);
                if ($indice !== null) {
                    throw new ConflictoEscritura($escrituras[$indice][1]);
                }
            }
            throw $e;
        }
    }

    private function indiceCondicionFallida(DynamoDbException $e): ?int
    {
        $razones = $e->get('CancellationReasons');
        if (is_array($razones)) {
            foreach ($razones as $indice => $razon) {
                if (($razon['Code'] ?? null) === 'ConditionalCheckFailed') {
                    return $indice;
                }
            }

            return null;
        }

        // DynamoDB Local a veces solo informa las razones en el mensaje: "[None, ConditionalCheckFailed]"
        if (preg_match('/\[([A-Za-z, ]+)\]/', (string) $e->getAwsErrorMessage(), $coincidencia) === 1) {
            $codigos = array_map('trim', explode(',', $coincidencia[1]));
            $indice = array_search('ConditionalCheckFailed', $codigos, true);

            return $indice === false ? null : $indice;
        }

        return null;
    }
}
