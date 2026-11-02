package com.agrosystem.gestion.application.campaign;

import java.util.UUID;

public record ComandoAnularCosto(UUID idMensaje, UUID idSaga, UUID idLabor, UUID idCampania, String origen) {
}
