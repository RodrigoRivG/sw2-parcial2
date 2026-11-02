package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import java.time.LocalDate;
import java.util.UUID;

public record EstadoResumidoCampania(
        UUID id, UUID idParcela, UUID idCultivo, EstadoCampania estado, LocalDate fechaInicio, LocalDate fechaFin) {
}
