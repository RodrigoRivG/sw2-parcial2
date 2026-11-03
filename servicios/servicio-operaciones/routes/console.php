<?php

use Illuminate\Support\Facades\Schedule;

// Tareas programadas (constitución §3: el scheduler es de Laravel). Las corre servicio-operaciones-programador.
Schedule::command('labores:revalidar-campanias')->everyMinute()->withoutOverlapping();
