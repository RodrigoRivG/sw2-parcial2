package com.agrosystem.gestion.domain.shared;

import java.math.BigDecimal;
import java.math.RoundingMode;

/** Monto en bolivianos con 2 decimales (README D-01). No redondea: el exceso de decimales es un error. */
public record Dinero(BigDecimal valor) {

    private static final int DECIMALES = 2;

    public static final Dinero CERO = new Dinero(BigDecimal.ZERO);

    public Dinero {
        valor = valor.setScale(DECIMALES, RoundingMode.UNNECESSARY);
    }

    public Dinero sumar(Dinero otro) {
        return new Dinero(valor.add(otro.valor));
    }

    public boolean esPositivo() {
        return valor.signum() > 0;
    }
}
