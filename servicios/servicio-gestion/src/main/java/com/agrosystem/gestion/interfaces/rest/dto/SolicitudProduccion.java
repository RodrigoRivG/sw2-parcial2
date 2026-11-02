package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.application.campaign.DatosProduccion;
import jakarta.validation.constraints.Digits;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.LocalDate;

public record SolicitudProduccion(
        @NotNull(message = "La cantidad es obligatoria.")
        @Digits(integer = 12, fraction = 2, message = "La cantidad admite hasta 12 enteros y 2 decimales.")
        BigDecimal cantidad,

        @NotNull(message = "La fecha de cosecha es obligatoria.")
        LocalDate fechaCosecha,

        @Size(max = 500, message = "Las observaciones admiten hasta 500 caracteres.")
        String observaciones) {

    /** Recorta antes de validar, para que los espacios no cuenten en la longitud (README D-09). */
    public SolicitudProduccion {
        observaciones = observaciones == null ? null : observaciones.trim();
    }

    public DatosProduccion aDatos() {
        return new DatosProduccion(cantidad, fechaCosecha, observaciones);
    }
}
