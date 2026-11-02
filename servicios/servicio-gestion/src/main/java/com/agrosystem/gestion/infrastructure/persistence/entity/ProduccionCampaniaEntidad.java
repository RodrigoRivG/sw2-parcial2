package com.agrosystem.gestion.infrastructure.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

@Entity
@Table(name = "produccion_campania")
public class ProduccionCampaniaEntidad {

    @Id
    @Column(name = "id_campania")
    private UUID idCampania;

    @Column(nullable = false, precision = 14, scale = 2)
    private BigDecimal cantidad;

    @Column(nullable = false, length = 20)
    private String unidad;

    @Column(name = "fecha_cosecha", nullable = false)
    private LocalDate fechaCosecha;

    @Column(length = 500)
    private String observaciones;

    @Column(name = "fecha_registro", nullable = false)
    private Instant fechaRegistro;

    @Column(name = "usuario_registro", nullable = false, length = 100)
    private String usuarioRegistro;

    protected ProduccionCampaniaEntidad() {
    }

    public ProduccionCampaniaEntidad(UUID idCampania) {
        this.idCampania = idCampania;
    }

    public void actualizar(
            BigDecimal cantidad,
            String unidad,
            LocalDate fechaCosecha,
            String observaciones,
            Instant fechaRegistro,
            String usuarioRegistro) {
        this.cantidad = cantidad;
        this.unidad = unidad;
        this.fechaCosecha = fechaCosecha;
        this.observaciones = observaciones;
        this.fechaRegistro = fechaRegistro;
        this.usuarioRegistro = usuarioRegistro;
    }

    public BigDecimal getCantidad() {
        return cantidad;
    }

    public String getUnidad() {
        return unidad;
    }

    public LocalDate getFechaCosecha() {
        return fechaCosecha;
    }

    public String getObservaciones() {
        return observaciones;
    }

    public Instant getFechaRegistro() {
        return fechaRegistro;
    }

    public String getUsuarioRegistro() {
        return usuarioRegistro;
    }
}
