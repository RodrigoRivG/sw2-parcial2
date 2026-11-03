<?php

use App\InterfaceAdapters\Http\Controllers\OpenApiControlador;
use App\InterfaceAdapters\Http\Controllers\SaludControlador;
use Illuminate\Support\Facades\Route;

// Rutas sin token y fuera del prefijo /api/operaciones/v1
Route::get('/salud', [SaludControlador::class, 'readiness']);
Route::get('/salud/liveness', [SaludControlador::class, 'liveness']);
Route::get('/salud/readiness', [SaludControlador::class, 'readiness']);
Route::get('/api-docs', OpenApiControlador::class);
