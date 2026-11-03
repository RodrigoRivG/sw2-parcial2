<?php

namespace App\Domain\Incident;

enum OrigenClasificacion: string
{
    /** TensorFlow Lite o TensorFlow.js en Flutter o Vue.js (RF-21). */
    case DISPOSITIVO = 'DISPOSITIVO';
    /** servicio-ia (RF-20). */
    case SERVIDOR = 'SERVIDOR';
}
