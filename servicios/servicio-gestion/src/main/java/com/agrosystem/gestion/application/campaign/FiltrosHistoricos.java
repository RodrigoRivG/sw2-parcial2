package com.agrosystem.gestion.application.campaign;

import java.time.LocalDate;
import java.util.UUID;

public record FiltrosHistoricos(
        UUID idCultivo, UUID idParcela, LocalDate fechaFinalizacionDesde, LocalDate fechaFinalizacionHasta) {
}
