<?php

namespace Tests\Support;

use App\InterfaceAdapters\Http\Security\ProveedorClavesJwt;
use Illuminate\Contracts\Console\Kernel;
use Illuminate\Foundation\Application;
use RuntimeException;
use Throwable;

/**
 * Ejecuta una tarea en N procesos reales (pcntl_fork) para las pruebas de concurrencia (README D-17).
 * Cada hijo arranca su propia aplicación, porque las conexiones HTTP del SDK no se comparten entre procesos.
 */
final class EnParalelo
{
    /**
     * @param  callable(Application, int): mixed  $tarea  recibe la aplicación del hijo y su número; devuelve un valor serializable
     * @param  callable(Application): void|null  $preparar  enlaces de prueba en la aplicación del hijo (dobles, reloj…)
     * @return list<array{ok: bool, valor?: mixed, error?: string}>
     */
    public static function ejecutar(int $procesos, callable $tarea, ?callable $preparar = null): array
    {
        $archivos = [];
        $pids = [];
        // El padre destruye su basura antes de crear los hijos: si no, un hijo podría destruir una copia heredada de
        // una conexión (por ejemplo, a RabbitMQ) y cerrarla por el socket que comparte con el padre, que después
        // esperaría respuestas que nunca llegan
        gc_collect_cycles();

        for ($i = 0; $i < $procesos; $i++) {
            $archivos[$i] = (string) tempnam(sys_get_temp_dir(), 'paralelo');
            $pid = pcntl_fork();
            if ($pid === -1) {
                throw new RuntimeException('No se pudo crear el proceso hijo.');
            }
            if ($pid === 0) {
                self::hijo($i, $archivos[$i], $tarea, $preparar);
            }
            $pids[] = $pid;
        }

        foreach ($pids as $pid) {
            pcntl_waitpid($pid, $estado);
        }

        $resultados = [];
        foreach ($archivos as $archivo) {
            $contenido = (string) file_get_contents($archivo);
            unlink($archivo);
            $resultados[] = $contenido === '' ? ['ok' => false, 'error' => 'El proceso hijo terminó sin resultado.'] : unserialize($contenido);
        }

        return $resultados;
    }

    private static function hijo(int $numero, string $archivo, callable $tarea, ?callable $preparar): never
    {
        // Lo heredado del padre no se recolecta en el hijo, por la misma razón
        gc_disable();
        try {
            $app = require __DIR__.'/../../bootstrap/app.php';
            $app->make(Kernel::class)->bootstrap();
            $app->singleton(ProveedorClavesJwt::class, Tokens::class);
            if ($preparar !== null) {
                $preparar($app);
            }
            $resultado = ['ok' => true, 'valor' => $tarea($app, $numero)];
        } catch (Throwable $e) {
            $resultado = ['ok' => false, 'error' => $e::class.': '.$e->getMessage()];
        }

        file_put_contents($archivo, serialize($resultado));
        // Sin funciones de cierre: las de PHPUnit y las del arranque de los tests son del proceso padre
        posix_kill((int) getmypid(), SIGKILL);
        exit(0);
    }
}
