package com.agrosystem.gestion.application.crop;

import com.agrosystem.gestion.domain.crop.UnidadProduccion;

public record DatosCultivo(String nombre, String variedad, UnidadProduccion unidadMedida, String descripcion) {
}
