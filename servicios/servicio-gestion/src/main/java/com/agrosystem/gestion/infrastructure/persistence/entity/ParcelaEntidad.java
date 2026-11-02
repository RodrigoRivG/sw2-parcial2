package com.agrosystem.gestion.infrastructure.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Version;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "parcela")
public class ParcelaEntidad {

    @Id
    private UUID id;

    @Column(nullable = false, length = 100)
    private String nombre;

    @Column(name = "superficie_hectareas", nullable = false, precision = 12, scale = 4)
    private BigDecimal superficieHectareas;

    @Column(length = 200)
    private String ubicacion;

    @Column(length = 500)
    private String descripcion;

    @Version
    private Long version;

    @Column(name = "fecha_creacion", nullable = false, updatable = false)
    private Instant fechaCreacion;

    @Column(name = "fecha_actualizacion", nullable = false)
    private Instant fechaActualizacion;

    protected ParcelaEntidad() {
    }

    public ParcelaEntidad(UUID id, Instant fechaCreacion) {
        this.id = id;
        this.fechaCreacion = fechaCreacion;
    }

    public void actualizar(
            String nombre,
            BigDecimal superficieHectareas,
            String ubicacion,
            String descripcion,
            Instant fechaActualizacion) {
        this.nombre = nombre;
        this.superficieHectareas = superficieHectareas;
        this.ubicacion = ubicacion;
        this.descripcion = descripcion;
        this.fechaActualizacion = fechaActualizacion;
    }

    public UUID getId() {
        return id;
    }

    public String getNombre() {
        return nombre;
    }

    public BigDecimal getSuperficieHectareas() {
        return superficieHectareas;
    }

    public String getUbicacion() {
        return ubicacion;
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
