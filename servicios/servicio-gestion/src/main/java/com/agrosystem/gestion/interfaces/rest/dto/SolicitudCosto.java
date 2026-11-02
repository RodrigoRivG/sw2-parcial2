package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.application.campaign.DatosCosto;
import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import jakarta.validation.constraints.Digits;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.LocalDate;

public record SolicitudCosto(
        @NotNull(message = "La categoría es obligatoria.")
        CategoriaCosto categoria,

        @NotNull(message = "El monto es obligatorio.")
        @Digits(integer = 12, fraction = 2, message = "El monto admite hasta 12 enteros y 2 decimales.")
        BigDecimal monto,

        @NotNull(message = "La fecha es obligatoria.")
        LocalDate fecha,

        @NotBlank(message = "La descripción es obligatoria.")
        @Size(max = 300, message = "La descripción admite hasta 300 caracteres.")
        String descripcion) {

    /** Recorta antes de validar, para que los espacios no cuenten en la longitud (README D-09). */
    public SolicitudCosto {
        descripcion = descripcion == null ? null : descripcion.trim();
    }

    public DatosCosto aDatos() {
        return new DatosCosto(categoria, monto, fecha, descripcion);
    }
}
