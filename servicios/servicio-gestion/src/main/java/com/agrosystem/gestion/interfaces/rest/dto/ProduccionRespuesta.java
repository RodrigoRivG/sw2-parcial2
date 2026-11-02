package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.domain.campaign.ProduccionCampania;
import com.agrosystem.gestion.domain.crop.UnidadProduccion;
import com.fasterxml.jackson.annotation.JsonFormat;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;

public record ProduccionRespuesta(
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal cantidad,
        UnidadProduccion unidad,
        LocalDate fechaCosecha,
        String observaciones,
        Instant fechaRegistro) {

    public static ProduccionRespuesta de(ProduccionCampania produccion) {
        return new ProduccionRespuesta(
                produccion.cantidad(),
                produccion.unidad(),
                produccion.fechaCosecha(),
                produccion.observaciones(),
                produccion.fechaRegistro());
    }
}
