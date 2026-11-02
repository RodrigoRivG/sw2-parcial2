package com.agrosystem.gestion.domain.campaign;

import java.time.LocalDate;
import java.util.UUID;

public record FiltrosCampania(
        EstadoCampania estado,
        UUID idParcela,
        UUID idCultivo,
        LocalDate fechaInicioDesde,
        LocalDate fechaInicioHasta,
        boolean soloNoFinalizadas) {

    public FiltrosCampania conSoloNoFinalizadas(boolean valor) {
        return new FiltrosCampania(estado, idParcela, idCultivo, fechaInicioDesde, fechaInicioHasta, valor);
    }
}
