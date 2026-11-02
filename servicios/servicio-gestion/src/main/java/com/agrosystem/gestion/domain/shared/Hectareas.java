package com.agrosystem.gestion.domain.shared;

import java.math.BigDecimal;
import java.math.RoundingMode;

/** Superficie en hectáreas: mayor a 0 y con 4 decimales (RN-01, README D-02). */
public record Hectareas(BigDecimal valor) {

    private static final int DECIMALES = 4;

    public Hectareas {
        if (valor == null
                || valor.signum() <= 0
                || valor.stripTrailingZeros().scale() > DECIMALES) {
            throw new ExcepcionDominio(
                    "SUPERFICIE_INVALIDA",
                    "La superficie debe ser mayor a 0, con hasta 4 decimales.",
                    ExcepcionDominio.Tipo.REGLA_NEGOCIO);
        }
        valor = valor.setScale(DECIMALES, RoundingMode.UNNECESSARY);
    }
}
