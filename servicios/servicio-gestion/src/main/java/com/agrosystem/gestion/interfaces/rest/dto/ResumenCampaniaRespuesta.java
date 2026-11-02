package com.agrosystem.gestion.interfaces.rest.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import java.math.BigDecimal;

/** Costos y producción se completan con spec-costos-manuales.md y spec-produccion.md. */
public record ResumenCampaniaRespuesta(
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal costoTotal,
        int cantidadCostos,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal produccion) {

    public static ResumenCampaniaRespuesta vacio() {
        return new ResumenCampaniaRespuesta(new BigDecimal("0.00"), 0, null);
    }
}
