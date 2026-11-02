package com.agrosystem.gestion.application.campaign;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.UUID;

public record ComandoRegistrarCosto(
        UUID idMensaje, UUID idSaga, UUID idLabor, UUID idCampania, BigDecimal monto, LocalDate fecha, String origen) {
}
