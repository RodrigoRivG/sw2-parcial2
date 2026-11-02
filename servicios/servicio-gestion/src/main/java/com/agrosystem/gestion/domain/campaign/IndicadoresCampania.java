package com.agrosystem.gestion.domain.campaign;

import com.agrosystem.gestion.domain.shared.Dinero;
import com.agrosystem.gestion.domain.shared.Hectareas;
import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;

/** Se calcula en cada consulta; un indicador sin datos es null con su motivo, nunca 0 (RN-03). */
public record IndicadoresCampania(
        Dinero costoTotal,
        BigDecimal rendimientoPorHectarea,
        BigDecimal costoPorHectarea,
        List<MotivoIndicadorNoDisponible> motivosNoDisponible,
        boolean definitivo) {

    private static final int DECIMALES = 2;

    /**
     * Recibe valores, no la campaña, para que también lo usen los históricos.
     * Un costoTotal de 0 significa que no hay costos vigentes, porque todo monto es mayor a 0.
     */
    public static IndicadoresCampania calcular(
            BigDecimal produccion, Dinero costoTotal, Hectareas superficie, EstadoCampania estado) {
        List<MotivoIndicadorNoDisponible> motivos = new ArrayList<>();
        if (produccion == null) {
            motivos.add(MotivoIndicadorNoDisponible.SIN_PRODUCCION);
        }
        if (!costoTotal.esPositivo()) {
            motivos.add(MotivoIndicadorNoDisponible.SIN_COSTOS);
        }
        boolean definitivo = estado == EstadoCampania.FINALIZADA;
        if (!motivos.isEmpty()) {
            return new IndicadoresCampania(costoTotal, null, null, List.copyOf(motivos), definitivo);
        }
        return new IndicadoresCampania(
                costoTotal,
                porHectarea(produccion, superficie),
                porHectarea(costoTotal.valor(), superficie),
                List.of(),
                definitivo);
    }

    private static BigDecimal porHectarea(BigDecimal valor, Hectareas superficie) {
        return valor.divide(superficie.valor(), MathContext.DECIMAL128).setScale(DECIMALES, RoundingMode.HALF_UP);
    }
}
