package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.application.campaign.DatosCampania;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;
import java.util.UUID;

public record ActualizarCampaniaSolicitud(
        @NotBlank(message = "El nombre es obligatorio.")
        @Size(max = 150, message = "El nombre admite hasta 150 caracteres.")
        String nombre,

        @NotNull(message = "La parcela es obligatoria.")
        UUID idParcela,

        @NotNull(message = "El cultivo es obligatorio.")
        UUID idCultivo,

        @NotNull(message = "La fecha de inicio es obligatoria.")
        LocalDate fechaInicio,

        @NotNull(message = "La fecha de fin es obligatoria.")
        LocalDate fechaFin,

        @NotNull(message = "La versión es obligatoria.")
        Long version) {

    /** Recorta antes de validar, para que los espacios no cuenten en la longitud (README D-09). */
    public ActualizarCampaniaSolicitud {
        nombre = nombre == null ? null : nombre.trim();
    }

    public DatosCampania aDatos() {
        return new DatosCampania(nombre, idParcela, idCultivo, fechaInicio, fechaFin);
    }
}
