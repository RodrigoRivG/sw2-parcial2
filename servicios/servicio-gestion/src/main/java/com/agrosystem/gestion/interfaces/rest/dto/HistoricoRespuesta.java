package com.agrosystem.gestion.interfaces.rest.dto;

import com.agrosystem.gestion.application.campaign.FilaHistorico;
import com.agrosystem.gestion.application.campaign.RegistroHistorico;
import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import com.agrosystem.gestion.domain.campaign.MotivoIndicadorNoDisponible;
import com.fasterxml.jackson.annotation.JsonFormat;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record HistoricoRespuesta(
        UUID idCampania,
        UUID idParcela,
        String nombreParcela,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal superficieHectareas,
        UUID idCultivo,
        String nombreCultivo,
        String variedad,
        LocalDate fechaInicio,
        LocalDate fechaFin,
        Instant fechaInicioEjecucion,
        Instant fechaFinalizacion,
        long duracionDias,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal produccion,
        LocalDate fechaCosecha,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal costoTotal,
        Map<CategoriaCosto, String> costosPorCategoria,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal rendimientoPorHectarea,
        @JsonFormat(shape = JsonFormat.Shape.STRING) BigDecimal costoPorHectarea,
        List<MotivoIndicadorNoDisponible> motivosNoDisponible) {

    public static HistoricoRespuesta de(RegistroHistorico registro) {
        FilaHistorico fila = registro.fila();
        Map<CategoriaCosto, String> costos = new EnumMap<>(CategoriaCosto.class);
        fila.costosPorCategoria().forEach((categoria, monto) -> costos.put(categoria, monto.valor().toPlainString()));
        LocalDate diaFinalizacion = fila.fechaFinalizacion().atOffset(ZoneOffset.UTC).toLocalDate();
        return new HistoricoRespuesta(
                fila.idCampania(),
                fila.idParcela(),
                fila.nombreParcela(),
                fila.superficie().valor(),
                fila.idCultivo(),
                fila.nombreCultivo(),
                fila.variedad(),
                fila.fechaInicio(),
                fila.fechaFin(),
                fila.fechaInicioEjecucion(),
                fila.fechaFinalizacion(),
                ChronoUnit.DAYS.between(fila.fechaInicio(), diaFinalizacion),
                fila.produccion(),
                fila.fechaCosecha(),
                fila.costoTotal().valor(),
                costos,
                registro.indicadores().rendimientoPorHectarea(),
                registro.indicadores().costoPorHectarea(),
                registro.indicadores().motivosNoDisponible());
    }
}
