package com.agrosystem.gestion.infrastructure.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "registro_auditoria")
public class RegistroAuditoriaEntidad {

    @Id
    private UUID id;

    @Column(nullable = false, length = 100)
    private String actor;

    @Column(nullable = false, length = 50)
    private String accion;

    @Column(nullable = false, length = 50)
    private String entidad;

    @Column(name = "id_entidad", nullable = false)
    private UUID idEntidad;

    @Column(name = "id_correlacion", length = 64)
    private String idCorrelacion;

    @Column(nullable = false)
    private Instant fecha;

    protected RegistroAuditoriaEntidad() {
    }

    public RegistroAuditoriaEntidad(
            UUID id,
            String actor,
            String accion,
            String entidad,
            UUID idEntidad,
            String idCorrelacion,
            Instant fecha) {
        this.id = id;
        this.actor = actor;
        this.accion = accion;
        this.entidad = entidad;
        this.idEntidad = idEntidad;
        this.idCorrelacion = idCorrelacion;
        this.fecha = fecha;
    }

    public String getActor() {
        return actor;
    }

    public String getAccion() {
        return accion;
    }

    public String getEntidad() {
        return entidad;
    }

    public UUID getIdEntidad() {
        return idEntidad;
    }

    public String getIdCorrelacion() {
        return idCorrelacion;
    }

    public Instant getFecha() {
        return fecha;
    }
}
