package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.application.plot.DatosParcela;
import jakarta.validation.constraints.Digits;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;

public record ActualizarParcelaSolicitud(
        @NotBlank(message = "El nombre es obligatorio.")
        @Size(max = 100, message = "El nombre admite hasta 100 caracteres.")
        String nombre,

        @NotNull(message = "La superficie es obligatoria.")
        @Digits(integer = 8, fraction = 4, message = "La superficie admite hasta 8 enteros y 4 decimales.")
        BigDecimal superficieHectareas,

        @Size(max = 200, message = "La ubicación admite hasta 200 caracteres.")
        String ubicacion,

        @Size(max = 500, message = "La descripción admite hasta 500 caracteres.")
        String descripcion,

        @NotNull(message = "La versión es obligatoria.")
        Long version) {

    /** Recorta antes de validar, para que los espacios no cuenten en la longitud (README D-09). */
    public ActualizarParcelaSolicitud {
        nombre = recortar(nombre);
        ubicacion = recortar(ubicacion);
        descripcion = recortar(descripcion);
    }

    public DatosParcela aDatos() {
        return new DatosParcela(nombre, superficieHectareas, ubicacion, descripcion);
    }

    private static String recortar(String texto) {
        return texto == null ? null : texto.trim();
    }
}
