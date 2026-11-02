package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.domain.plot.Parcela;
import com.fasterxml.jackson.annotation.JsonFormat;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public record ParcelaRespuesta(
        UUID id,
        String nombre,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal superficieHectareas,
        String ubicacion,
        String descripcion,
        Long version,
        Instant fechaCreacion,
        Instant fechaActualizacion) {

    public static ParcelaRespuesta de(Parcela parcela) {
        return new ParcelaRespuesta(
                parcela.getId(),
                parcela.getNombre(),
                parcela.getSuperficie().valor(),
                parcela.getUbicacion(),
                parcela.getDescripcion(),
                parcela.getVersion(),
                parcela.getFechaCreacion(),
                parcela.getFechaActualizacion());
    }
}
