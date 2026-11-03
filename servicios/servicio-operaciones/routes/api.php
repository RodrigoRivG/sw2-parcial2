<?php

use App\InterfaceAdapters\Http\Controllers\IncidenciaControlador;
use App\InterfaceAdapters\Http\Controllers\LaborControlador;
use App\InterfaceAdapters\Http\Controllers\SagaControlador;
use App\InterfaceAdapters\Http\Controllers\SincronizacionControlador;
use App\InterfaceAdapters\Http\Middleware\ExigirJsonValido;
use Illuminate\Support\Facades\Route;

// Prefijo /api/operaciones/v1 (bootstrap/app.php). Toda ruta exige JWT (constitución §9).
Route::middleware(['jwt', ExigirJsonValido::class])->group(function (): void {
    // Labores (spec-labores.md). Las reglas que dependen del cuerpo o del recurso las aplica el caso de uso.
    Route::post('/labores', [LaborControlador::class, 'crear'])->middleware('rol:administrador,tecnico_campo');
    Route::post('/labores/{id}/realizacion', [LaborControlador::class, 'realizar'])->whereUuid('id')->middleware('rol:tecnico_campo');
    Route::post('/labores/{id}/resolucion', [LaborControlador::class, 'resolver'])->whereUuid('id')->middleware('rol:administrador');
    Route::get('/labores', [LaborControlador::class, 'listar'])->middleware('rol:administrador,gerencia,lectura_operaciones,tecnico_campo');
    Route::get('/labores/{id}', [LaborControlador::class, 'detalle'])->whereUuid('id')->middleware('rol:administrador,gerencia,lectura_operaciones,tecnico_campo');

    // Incidencias (spec-incidencias.md); el registro es multipart/form-data
    Route::post('/incidencias', [IncidenciaControlador::class, 'crear'])->middleware('rol:tecnico_campo');
    Route::get('/incidencias', [IncidenciaControlador::class, 'listar'])->middleware('rol:administrador,gerencia,lectura_operaciones,tecnico_campo');
    Route::get('/incidencias/{id}', [IncidenciaControlador::class, 'detalle'])->whereUuid('id')->middleware('rol:administrador,gerencia,lectura_operaciones,tecnico_campo');

    // Sincronización offline por lotes (spec-sincronizacion.md); multipart/form-data
    Route::post('/sincronizacion', [SincronizacionControlador::class, 'sincronizar'])->middleware('rol:tecnico_campo');

    // Saga (spec-saga.md)
    Route::get('/sagas/{id}', [SagaControlador::class, 'detalle'])->whereUuid('id')->middleware('rol:administrador,gerencia,lectura_operaciones');
});
