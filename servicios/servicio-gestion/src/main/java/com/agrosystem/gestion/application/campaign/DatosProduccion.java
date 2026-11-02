package com.agrosystem.gestion.application.campaign;

import java.math.BigDecimal;
import java.time.LocalDate;

public record DatosProduccion(BigDecimal cantidad, LocalDate fechaCosecha, String observaciones) {
}
