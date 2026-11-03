<?php

namespace Tests\Support;

use App\Application\Contracts\Reloj;
use App\Infrastructure\Messaging\TopologiaSaga;
use App\Infrastructure\Persistence\DynamoDb\NombresTablas;
use Aws\DynamoDb\DynamoDbClient;
use PHPUnit\Framework\Assert;
use Tests\TestCase;

/**
 * Escenarios de la Saga para los tests de integración: registra una labor con insumos y avanza
 * respondiendo como inventario o gestión (spec-saga.md 2.9).
 */
final class FlujoSaga
{
    public string $idLabor;

    public string $idSaga;

    public string $parcela;

    public string $campania;

    /** @var array<string, mixed> el DescontarInsumos recibido por inventario */
    public array $descontar;

    public function __construct(private readonly TestCase $test) {}

    public static function preparar(TestCase $test): self
    {
        self::vaciarSagas();
        RabbitPruebas::purgarTodo();
        GestionFalsa::instalar();
        $flujo = new self($test);
        $flujo->parcela = DatosLabor::uuid();
        $flujo->campania = DatosLabor::uuid();
        GestionFalsa::campania($flujo->campania, $flujo->parcela);

        return $flujo;
    }

    /** Registra la labor y lee el DescontarInsumos que recibe inventario. */
    public function registrar(string ...$cantidades): self
    {
        $cuerpo = DatosLabor::realizada($this->parcela, $this->campania, ['insumos' => DatosLabor::insumos(...($cantidades ?: ['100', '2.5']))]);
        $respuesta = $this->test->postJson('/api/operaciones/v1/labores', $cuerpo, $this->tecnico())->assertCreated();
        $this->idLabor = $cuerpo['idOperacion'];
        $this->idSaga = (string) $respuesta->json('idSaga');
        $this->descontar = $this->comandoA(TopologiaSaga::COLA_INVENTARIO, 'DescontarInsumos');

        return $this;
    }

    /** Responde y procesa la respuesta con el consumidor del servicio. */
    public function responder(string $tipo, array $datos = [], ?string $idMensaje = null): self
    {
        $origen = str_starts_with($tipo, 'Insumos') ? 'servicio-inventario' : 'servicio-gestion';
        RabbitPruebas::responder($tipo, $this->idSaga, ['idLabor' => $this->idLabor, ...$datos], $idMensaje, $origen);
        Assert::assertSame(1, RabbitPruebas::procesarRespuestas(1), "El consumidor no procesó {$tipo}.");

        return $this;
    }

    public function descontado(string $costoTotal = '580.50'): self
    {
        return $this->responder('InsumosDescontados', ['costoTotal' => $costoTotal, 'items' => []]);
    }

    /** @return array<string, mixed> el siguiente comando de esa cola, que debe ser del tipo indicado */
    public function comandoA(string $cola, string $tipo): array
    {
        $sobre = RabbitPruebas::leer($cola);
        Assert::assertNotNull($sobre, "No llegó {$tipo} a {$cola}.");
        Assert::assertSame($tipo, $sobre['tipo']);
        Assert::assertSame($this->idSaga ?? $sobre['idCorrelacion'], $sobre['idCorrelacion']);

        return $sobre;
    }

    public function sinComandos(): void
    {
        Assert::assertSame(0, RabbitPruebas::contar(TopologiaSaga::COLA_INVENTARIO), 'Inventario recibió un comando de más.');
        Assert::assertSame(0, RabbitPruebas::contar(TopologiaSaga::COLA_GESTION), 'Gestión recibió un comando de más.');
    }

    /** Corre la recuperación como si el reloj marcara ahora + $segundos. */
    public function vencer(int $segundos): self
    {
        app()->instance(Reloj::class, new RelojFijo(DatosLabor::fecha("+{$segundos} seconds")));
        $this->test->artisan('sagas:reanudar')->assertSuccessful();

        return $this;
    }

    /** @return array<string, mixed> */
    public function labor(): array
    {
        return $this->test->getJson("/api/operaciones/v1/labores/{$this->idLabor}", $this->test->encabezados(['gerencia']))->assertOk()->json();
    }

    /** "ESTADO/CODIGO_DEL_MOTIVO" de la labor, para comparar en una sola línea. */
    public function estadoLabor(): string
    {
        $labor = $this->labor();

        return $labor['estado'].'/'.($labor['motivo']['codigo'] ?? '-');
    }

    /** @return array<string, mixed> */
    public function saga(): array
    {
        return $this->test->getJson("/api/operaciones/v1/sagas/{$this->idSaga}", $this->test->encabezados(['administrador']))->assertOk()->json();
    }

    /**
     * La recuperación atiende todas las Sagas vencidas: sin esto, una Saga que otro test dejó activa
     * reenviaría sus comandos a las colas de este test.
     */
    public static function vaciarSagas(): void
    {
        $cliente = app(DynamoDbClient::class);
        $tabla = app(NombresTablas::class)->de('sagas');
        $parametros = ['TableName' => $tabla, 'ProjectionExpression' => 'id_saga'];
        do {
            $resultado = $cliente->scan($parametros);
            foreach (array_chunk($resultado['Items'] ?? [], 25) as $lote) {
                $cliente->batchWriteItem(['RequestItems' => [$tabla => array_map(
                    fn ($item) => ['DeleteRequest' => ['Key' => ['id_saga' => $item['id_saga']]]],
                    $lote,
                )]]);
            }
            $parametros['ExclusiveStartKey'] = $resultado['LastEvaluatedKey'] ?? null;
        } while ($parametros['ExclusiveStartKey'] !== null);
    }

    /** @return list<string> acciones auditadas de la entidad */
    public static function auditorias(string $entidad, string $id): array
    {
        $resultado = app(DynamoDbClient::class)->query([
            'TableName' => app(NombresTablas::class)->de('registros_auditoria'),
            'IndexName' => 'gsi_entidad',
            'KeyConditionExpression' => 'entidad_id = :e',
            'ExpressionAttributeValues' => [':e' => ['S' => "{$entidad}#{$id}"]],
        ]);
        $items = $resultado['Items'];
        usort($items, fn ($a, $b) => $a['fecha']['S'] <=> $b['fecha']['S']);

        return array_map(fn ($item) => $item['accion']['S'], $items);
    }

    /** @return array<string, string> */
    public function tecnico(): array
    {
        return $this->test->encabezados(['tecnico_campo'], 'tec-ana');
    }
}
