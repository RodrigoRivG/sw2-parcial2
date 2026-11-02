package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.application.crop.DatosCultivo;
import com.agrosystem.gestion.domain.crop.UnidadProduccion;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record ActualizarCultivoSolicitud(
        @NotBlank(message = "El nombre es obligatorio.")
        @Size(max = 100, message = "El nombre admite hasta 100 caracteres.")
        String nombre,

        @Size(max = 100, message = "La variedad admite hasta 100 caracteres.")
        String variedad,

        @NotNull(message = "La unidad de medida es obligatoria.")
        UnidadProduccion unidadMedida,

        @Size(max = 500, message = "La descripción admite hasta 500 caracteres.")
        String descripcion,

        @NotNull(message = "La versión es obligatoria.")
        Long version) {

    /** Recorta antes de validar, para que los espacios no cuenten en la longitud (README D-09). */
    public ActualizarCultivoSolicitud {
        nombre = recortar(nombre);
        variedad = recortar(variedad);
        descripcion = recortar(descripcion);
    }

    public DatosCultivo aDatos() {
        return new DatosCultivo(nombre, variedad, unidadMedida, descripcion);
    }

    private static String recortar(String texto) {
        return texto == null ? null : texto.trim();
    }
}
