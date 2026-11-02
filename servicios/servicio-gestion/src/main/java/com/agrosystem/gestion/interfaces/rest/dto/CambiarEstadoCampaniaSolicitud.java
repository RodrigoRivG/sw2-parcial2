package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import jakarta.validation.constraints.NotNull;

public record CambiarEstadoCampaniaSolicitud(
        @NotNull(message = "El estado de destino es obligatorio.")
        EstadoCampania estadoDestino,

        @NotNull(message = "La versión es obligatoria.")
        Long version) {
}
