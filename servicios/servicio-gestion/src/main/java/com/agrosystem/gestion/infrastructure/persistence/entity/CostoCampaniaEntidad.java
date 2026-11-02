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
@Table(name = "costo_campania")
public class CostoCampaniaEntidad {

    @Id
    private UUID id;

    /** Solo lectura, para filtrar el listado: la relación la escribe CampaniaEntidad. */
    @Column(name = "id_campania", insertable = false, updatable = false)
    private UUID idCampania;

    @Column(nullable = false, length = 20)
    private String categoria;

    @Column(nullable = false, precision = 14, scale = 2)
    private BigDecimal monto;

    @Column(nullable = false)
    private LocalDate fecha;

    @Column(nullable = false, length = 300)
    private String descripcion;

    @Column(nullable = false, length = 10, updatable = false)
    private String origen;

    @Column(name = "id_saga", updatable = false)
    private UUID idSaga;

    @Column(name = "id_labor", updatable = false)
    private UUID idLabor;

    @Column(nullable = false)
    private boolean anulado;

    @Column(name = "fecha_anulacion")
    private Instant fechaAnulacion;

    @Column(name = "fecha_registro", nullable = false, updatable = false)
    private Instant fechaRegistro;

    protected CostoCampaniaEntidad() {
    }

    public CostoCampaniaEntidad(UUID id, String origen, UUID idSaga, UUID idLabor, Instant fechaRegistro) {
        this.id = id;
        this.origen = origen;
        this.idSaga = idSaga;
        this.idLabor = idLabor;
        this.fechaRegistro = fechaRegistro;
    }

    public void actualizar(
            String categoria,
            BigDecimal monto,
            LocalDate fecha,
            String descripcion,
            boolean anulado,
            Instant fechaAnulacion) {
        this.categoria = categoria;
        this.monto = monto;
        this.fecha = fecha;
        this.descripcion = descripcion;
        this.anulado = anulado;
        this.fechaAnulacion = fechaAnulacion;
    }

    public UUID getId() {
        return id;
    }

    public UUID getIdCampania() {
        return idCampania;
    }

    public String getCategoria() {
        return categoria;
    }

    public BigDecimal getMonto() {
        return monto;
    }

    public LocalDate getFecha() {
        return fecha;
    }

    public String getDescripcion() {
        return descripcion;
    }

    public String getOrigen() {
        return origen;
    }

    public UUID getIdSaga() {
        return idSaga;
    }

    public UUID getIdLabor() {
        return idLabor;
    }

    public boolean isAnulado() {
        return anulado;
    }

    public Instant getFechaAnulacion() {
        return fechaAnulacion;
    }

    public Instant getFechaRegistro() {
        return fechaRegistro;
    }
}
