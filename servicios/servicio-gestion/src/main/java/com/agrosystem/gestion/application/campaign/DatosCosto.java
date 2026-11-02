package com.agrosystem.gestion.application.campaign;

import com.agrosystem.gestion.domain.campaign.CategoriaCosto;
import java.math.BigDecimal;
import java.time.LocalDate;

public record DatosCosto(CategoriaCosto categoria, BigDecimal monto, LocalDate fecha, String descripcion) {
}
