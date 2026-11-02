package com.agrosystem.gestion.application.campaign;

import java.time.LocalDate;
import java.util.UUID;

public record DatosCampania(String nombre, UUID idParcela, UUID idCultivo, LocalDate fechaInicio, LocalDate fechaFin) {
}
