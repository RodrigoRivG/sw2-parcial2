package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import com.agrosystem.gestion.domain.campaign.CostoCampania;
import com.agrosystem.gestion.domain.campaign.OrigenCosto;
import com.fasterxml.jackson.annotation.JsonFormat;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

public record CostoRespuesta(
        UUID id,
        CategoriaCosto categoria,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal monto,
        LocalDate fecha,
        String descripcion,
        OrigenCosto origen,
        UUID idLabor,
        Instant fechaRegistro) {

    public static CostoRespuesta de(CostoCampania costo) {
        return new CostoRespuesta(
                costo.getId(),
                costo.getCategoria(),
                costo.getMonto().valor(),
                costo.getFecha(),
                costo.getDescripcion(),
                costo.getOrigen(),
                costo.getIdLabor(),
                costo.getFechaRegistro());
    }
}
