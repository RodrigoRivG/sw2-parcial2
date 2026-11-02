package com.agrosystem.gestion.domain.campaign;

import com.agrosystem.gestion.domain.crop.UnidadProduccion;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.LocalDate;

/** Producción total de la campaña. Una cantidad de 0 es una pérdida total: un dato real. */
public record ProduccionCampania(
        BigDecimal cantidad,
        UnidadProduccion unidad,
        LocalDate fechaCosecha,
        String observaciones,
        Instant fechaRegistro,
        String usuarioRegistro) {

    private static final int DECIMALES = 2;

    static ProduccionCampania crear(
            BigDecimal cantidad,
            UnidadProduccion unidad,
            LocalDate fechaCosecha,
            String observaciones,
            LocalDate fechaInicioCampania,
            LocalDate hoy,
            String usuario,
            Instant ahora) {
        if (cantidad.signum() < 0) {
            throw new ExcepcionDominio(
                    "PRODUCCION_INVALIDA", "La cantidad no puede ser negativa.", ExcepcionDominio.Tipo.REGLA_NEGOCIO);
        }
        if (fechaCosecha.isBefore(fechaInicioCampania) || fechaCosecha.isAfter(hoy)) {
            throw new ExcepcionDominio(
                    "FECHA_COSECHA_INVALIDA",
                    "La fecha de cosecha debe estar entre el inicio de la campaña y hoy.",
                    ExcepcionDominio.Tipo.REGLA_NEGOCIO);
        }
        String textoObservaciones = observaciones == null || observaciones.isBlank() ? null : observaciones.trim();
        return new ProduccionCampania(
                cantidad.setScale(DECIMALES, RoundingMode.UNNECESSARY),
                unidad,
                fechaCosecha,
                textoObservaciones,
                ahora,
                usuario);
    }
}
