package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.fasterxml.jackson.annotation.JsonFormat;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

/** Elementos del listado y vista de tecnico_campo: sin el resumen económico. */
public record CampaniaSinResumenRespuesta(
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
        Long version,
        Instant fechaCreacion,
        Instant fechaActualizacion) {

    public static CampaniaSinResumenRespuesta de(Campania campania) {
        return new CampaniaSinResumenRespuesta(
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
                campania.getVersion(),
                campania.getFechaCreacion(),
                campania.getFechaActualizacion());
    }
}
