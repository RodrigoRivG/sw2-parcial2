package com.agrosystem.gestion.infrastructure.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Version;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

@Entity
@Table(name = "campania")
public class CampaniaEntidad {

    @Id
    private UUID id;

    @Column(nullable = false, length = 150)
    private String nombre;

    @Column(name = "id_parcela", nullable = false)
    private UUID idParcela;

    @Column(name = "id_cultivo", nullable = false)
    private UUID idCultivo;

    @Column(name = "fecha_inicio", nullable = false)
    private LocalDate fechaInicio;

    @Column(name = "fecha_fin", nullable = false)
    private LocalDate fechaFin;

    @Column(name = "superficie_hectareas", nullable = false, precision = 12, scale = 4)
    private BigDecimal superficieHectareas;

    @Column(nullable = false, length = 20)
    private String estado;

    @Column(name = "fecha_inicio_ejecucion")
    private Instant fechaInicioEjecucion;

    @Column(name = "fecha_finalizacion")
    private Instant fechaFinalizacion;

    @Version
    private Long version;

    @Column(name = "fecha_creacion", nullable = false, updatable = false)
    private Instant fechaCreacion;

    @Column(name = "fecha_actualizacion", nullable = false)
    private Instant fechaActualizacion;

    protected CampaniaEntidad() {
    }

    public CampaniaEntidad(UUID id, Instant fechaCreacion) {
        this.id = id;
        this.fechaCreacion = fechaCreacion;
    }

    public void actualizar(
            String nombre,
            UUID idParcela,
            UUID idCultivo,
            LocalDate fechaInicio,
            LocalDate fechaFin,
            BigDecimal superficieHectareas,
            String estado,
            Instant fechaInicioEjecucion,
            Instant fechaFinalizacion,
            Instant fechaActualizacion) {
        this.nombre = nombre;
        this.idParcela = idParcela;
        this.idCultivo = idCultivo;
        this.fechaInicio = fechaInicio;
        this.fechaFin = fechaFin;
        this.superficieHectareas = superficieHectareas;
        this.estado = estado;
        this.fechaInicioEjecucion = fechaInicioEjecucion;
        this.fechaFinalizacion = fechaFinalizacion;
        this.fechaActualizacion = fechaActualizacion;
    }

    public UUID getId() {
        return id;
    }

    public String getNombre() {
        return nombre;
    }

    public UUID getIdParcela() {
        return idParcela;
    }

    public UUID getIdCultivo() {
        return idCultivo;
    }

    public LocalDate getFechaInicio() {
        return fechaInicio;
    }

    public LocalDate getFechaFin() {
        return fechaFin;
    }

    public BigDecimal getSuperficieHectareas() {
        return superficieHectareas;
    }

    public String getEstado() {
        return estado;
    }

    public Instant getFechaInicioEjecucion() {
        return fechaInicioEjecucion;
    }

    public Instant getFechaFinalizacion() {
        return fechaFinalizacion;
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
