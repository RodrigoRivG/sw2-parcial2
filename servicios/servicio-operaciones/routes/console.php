<?php

use Illuminate\Support\Facades\Schedule;

// Tareas programadas (constitución §3: el scheduler es de Laravel). Las corre servicio-operaciones-programador.
// Caducidad del bloqueo de solapamiento en minutos (spec-saga.md RQ-SAG-14): sin argumento, Laravel usa 1.440 min,
// y un bloqueo huérfano (proceso terminado con SIGKILL) frenaría la tarea un día entero. No garantiza exclusión:
// si una ejecución supera la caducidad, la siguiente puede solaparse; lo controlan las escrituras condicionales.
Schedule::command('labores:revalidar-campanias')->everyMinute()->withoutOverlapping(5);
Schedule::command('sagas:reanudar')->everyTenSeconds()->withoutOverlapping(2);
Schedule::command('incidencias:republicar-eventos')->everyMinute()->withoutOverlapping(5);
