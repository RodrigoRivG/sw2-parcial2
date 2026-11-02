package com.agrosystem.gestion.infrastructure.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "saga_procesada")
public class SagaProcesadaEntidad {

    @Id
    @Column(name = "id_saga")
    private UUID idSaga;

    @Column(nullable = false, length = 20)
    private String resultado;

    @Column(name = "id_campania")
    private UUID idCampania;

    @Column(name = "id_labor")
    private UUID idLabor;

    @Column(name = "id_costo")
    private UUID idCosto;

    @Column(precision = 14, scale = 2)
    private BigDecimal monto;

    @Column(length = 50)
    private String codigo;

    @Column(length = 300)
    private String motivo;

    @Column(name = "anulacion_resultado", length = 20)
    private String anulacionResultado;

    @Column(name = "anulacion_sin_efecto")
    private Boolean anulacionSinEfecto;

    @Column(name = "anulacion_codigo", length = 50)
    private String anulacionCodigo;

    @Column(name = "fecha_procesamiento", nullable = false)
    private Instant fechaProcesamiento;

    @Column(name = "fecha_actualizacion", nullable = false)
    private Instant fechaActualizacion;

    protected SagaProcesadaEntidad() {
    }

    public SagaProcesadaEntidad(UUID idSaga) {
        this.idSaga = idSaga;
    }

    public void actualizar(
            String resultado,
            UUID idCampania,
            UUID idLabor,
            UUID idCosto,
            BigDecimal monto,
            String codigo,
            String motivo,
            String anulacionResultado,
            Boolean anulacionSinEfecto,
            String anulacionCodigo,
            Instant fechaProcesamiento,
            Instant fechaActualizacion) {
        this.resultado = resultado;
        this.idCampania = idCampania;
        this.idLabor = idLabor;
        this.idCosto = idCosto;
        this.monto = monto;
        this.codigo = codigo;
        this.motivo = motivo;
        this.anulacionResultado = anulacionResultado;
        this.anulacionSinEfecto = anulacionSinEfecto;
        this.anulacionCodigo = anulacionCodigo;
        this.fechaProcesamiento = fechaProcesamiento;
        this.fechaActualizacion = fechaActualizacion;
    }

    public UUID getIdSaga() {
        return idSaga;
    }

    public String getResultado() {
        return resultado;
    }

    public UUID getIdCampania() {
        return idCampania;
    }

    public UUID getIdLabor() {
        return idLabor;
    }

    public UUID getIdCosto() {
        return idCosto;
    }

    public BigDecimal getMonto() {
        return monto;
    }

    public String getCodigo() {
        return codigo;
    }

    public String getMotivo() {
        return motivo;
    }

    public String getAnulacionResultado() {
        return anulacionResultado;
    }

    public Boolean getAnulacionSinEfecto() {
        return anulacionSinEfecto;
    }

    public String getAnulacionCodigo() {
        return anulacionCodigo;
    }

    public Instant getFechaProcesamiento() {
        return fechaProcesamiento;
    }

    public Instant getFechaActualizacion() {
        return fechaActualizacion;
    }
}
