package com.agrosystem.gestion.infrastructure.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "mensaje_procesado")
public class MensajeProcesadoEntidad {

    @Id
    @Column(name = "id_mensaje")
    private UUID idMensaje;

    @Column(name = "id_saga", nullable = false)
    private UUID idSaga;

    @Column(name = "fecha_procesamiento", nullable = false)
    private Instant fechaProcesamiento;

    protected MensajeProcesadoEntidad() {
    }

    public MensajeProcesadoEntidad(UUID idMensaje, UUID idSaga, Instant fechaProcesamiento) {
        this.idMensaje = idMensaje;
        this.idSaga = idSaga;
        this.fechaProcesamiento = fechaProcesamiento;
    }
}
