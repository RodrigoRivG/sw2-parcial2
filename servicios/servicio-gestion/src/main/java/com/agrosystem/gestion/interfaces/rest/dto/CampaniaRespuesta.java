package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.fasterxml.jackson.annotation.JsonFormat;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

public record CampaniaRespuesta(
        UUID id,
        String nombre,
        UUID idParcela,
        UUID idCultivo,
        LocalDate fechaInicio,
        LocalDate fechaFin,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal superficieHectareas,
        EstadoCampania estado,
        Instant fechaInicioEjecucion,
        Instant fechaFinalizacion,
        ResumenCampaniaRespuesta resumen,
        Long version,
        Instant fechaCreacion,
        Instant fechaActualizacion) {

    public static CampaniaRespuesta de(Campania campania) {
        return new CampaniaRespuesta(
                campania.getId(),
                campania.getNombre(),
                campania.getIdParcela(),
                campania.getIdCultivo(),
                campania.getFechaInicio(),
                campania.getFechaFin(),
                campania.getSuperficie().valor(),
                campania.getEstado(),
                campania.getFechaInicioEjecucion(),
                campania.getFechaFinalizacion(),
                ResumenCampaniaRespuesta.de(campania),
                campania.getVersion(),
                campania.getFechaCreacion(),
                campania.getFechaActualizacion());
    }
}
