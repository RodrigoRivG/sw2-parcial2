package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.application.campaign.ResultadoIndicadores;
import com.agrosystem.gestion.domain.campaign.Campania;
import com.agrosystem.gestion.domain.campaign.EstadoCampania;
import com.agrosystem.gestion.domain.campaign.IndicadoresCampania;
import com.agrosystem.gestion.domain.campaign.MotivoIndicadorNoDisponible;
import com.fasterxml.jackson.annotation.JsonFormat;
import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

public record IndicadoresRespuesta(
        UUID idCampania,
        EstadoCampania estadoCampania,
        boolean definitivo,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal superficieHectareas,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal produccion,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal costoTotal,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal rendimientoPorHectarea,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal costoPorHectarea,
        List<MotivoIndicadorNoDisponible> motivosNoDisponible) {

    public static IndicadoresRespuesta de(ResultadoIndicadores resultado) {
        Campania campania = resultado.campania();
        IndicadoresCampania indicadores = resultado.indicadores();
        return new IndicadoresRespuesta(
                campania.getId(),
                campania.getEstado(),
                indicadores.definitivo(),
                campania.getSuperficie().valor(),
                campania.tieneProduccion() ? campania.getProduccion().cantidad() : null,
                indicadores.costoTotal().valor(),
                indicadores.rendimientoPorHectarea(),
                indicadores.costoPorHectarea(),
                indicadores.motivosNoDisponible());
    }
}
