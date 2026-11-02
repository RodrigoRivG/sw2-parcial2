package com.agrosystem.gestion.infrastructure.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Version;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "cultivo")
public class CultivoEntidad {

    @Id
    private UUID id;

    @Column(nullable = false, length = 100)
    private String nombre;

    @Column(length = 100)
    private String variedad;

    @Column(name = "unidad_medida", nullable = false, length = 20, updatable = false)
    private String unidadMedida;

    @Column(length = 500)
    private String descripcion;

    @Version
    private Long version;

    @Column(name = "fecha_creacion", nullable = false, updatable = false)
    private Instant fechaCreacion;

    @Column(name = "fecha_actualizacion", nullable = false)
    private Instant fechaActualizacion;

    protected CultivoEntidad() {
    }

    public CultivoEntidad(UUID id, String unidadMedida, Instant fechaCreacion) {
        this.id = id;
        this.unidadMedida = unidadMedida;
        this.fechaCreacion = fechaCreacion;
    }

    public void actualizar(String nombre, String variedad, String descripcion, Instant fechaActualizacion) {
        this.nombre = nombre;
        this.variedad = variedad;
        this.descripcion = descripcion;
        this.fechaActualizacion = fechaActualizacion;
    }

    public UUID getId() {
        return id;
    }

    public String getNombre() {
        return nombre;
    }

    public String getVariedad() {
        return variedad;
    }

    public String getUnidadMedida() {
        return unidadMedida;
    }

    public String getDescripcion() {
        return descripcion;
    }

    public Long getVersion() {
        return version;
    }

    public Instant getFechaCreacion() {
        return fechaCreacion;
    }

    public Instant getFechaActualizacion() {
        return fechaActualizacion;
    }
}
