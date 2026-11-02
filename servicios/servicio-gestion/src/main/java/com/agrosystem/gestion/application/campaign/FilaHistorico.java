package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import com.agrosystem.gestion.domain.shared.Dinero;
import com.agrosystem.gestion.domain.shared.Hectareas;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.Map;
import java.util.UUID;

/** Fila plana de la consulta de históricos; no es un agregado. */
public record FilaHistorico(
        UUID idCampania,
        UUID idParcela,
        String nombreParcela,
        Hectareas superficie,
        UUID idCultivo,
        String nombreCultivo,
        String variedad,
        LocalDate fechaInicio,
        LocalDate fechaFin,
        Instant fechaInicioEjecucion,
        Instant fechaFinalizacion,
        BigDecimal produccion,
        LocalDate fechaCosecha,
        Dinero costoTotal,
        Map<CategoriaCosto, Dinero> costosPorCategoria) {
}
