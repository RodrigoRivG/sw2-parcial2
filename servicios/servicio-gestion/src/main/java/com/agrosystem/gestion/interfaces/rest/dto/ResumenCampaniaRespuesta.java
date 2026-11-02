package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.domain.campaign.Campania;
import com.fasterxml.jackson.annotation.JsonFormat;
import java.math.BigDecimal;

public record ResumenCampaniaRespuesta(
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal costoTotal,
        int cantidadCostos,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal produccion) {

    public static ResumenCampaniaRespuesta de(Campania campania) {
        return new ResumenCampaniaRespuesta(
                campania.costoTotal().valor(),
                campania.cantidadCostos(),
                campania.tieneProduccion() ? campania.getProduccion().cantidad() : null);
    }
}
