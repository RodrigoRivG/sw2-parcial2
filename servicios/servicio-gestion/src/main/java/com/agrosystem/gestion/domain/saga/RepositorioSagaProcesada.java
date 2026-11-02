package com.agrosystem.gestion.domain.saga;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

public interface RepositorioSagaProcesada {

    /** Serializa los comandos del mismo idSaga hasta que termine la transacción (RQ-SAG-11). */
    void bloquear(UUID idSaga);

    Optional<SagaProcesada> buscar(UUID idSaga);

    void guardar(SagaProcesada saga);

    /** Registra el mensaje una sola vez, aunque se entregue varias veces. */
    void registrarMensaje(UUID idMensaje, UUID idSaga, Instant ahora);
}
