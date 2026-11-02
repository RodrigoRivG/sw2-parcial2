package com.agrosystem.gestion.domain.saga;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/** Resultado guardado por idSaga: garantiza la idempotencia y rechaza registros tardíos tras una anulación. */
public class SagaProcesada {

    public static final String ANULACION_APLICADA = "ANULADO";
    public static final String ANULACION_RECHAZADA = "RECHAZADA";

    private final UUID idSaga;
    private ResultadoSagaProcesada resultado;
    private final UUID idCampania;
    private final UUID idLabor;
    private final UUID idCosto;
    private final BigDecimal monto;
    private final String codigo;
    private final String motivo;
    private String anulacionResultado;
    private Boolean anulacionSinEfecto;
    private String anulacionCodigo;
    private final Instant fechaProcesamiento;
    private Instant fechaActualizacion;

    public SagaProcesada(
            UUID idSaga,
            ResultadoSagaProcesada resultado,
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
        this.idSaga = idSaga;
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

    public static SagaProcesada registrada(
            UUID idSaga, UUID idCampania, UUID idLabor, UUID idCosto, BigDecimal monto, Instant ahora) {
        return new SagaProcesada(idSaga, ResultadoSagaProcesada.REGISTRADO, idCampania, idLabor, idCosto, monto,
                null, null, null, null, null, ahora, ahora);
    }

    public static SagaProcesada rechazada(
            UUID idSaga, UUID idCampania, UUID idLabor, String codigo, String motivo, Instant ahora) {
        return new SagaProcesada(idSaga, ResultadoSagaProcesada.RECHAZADO, idCampania, idLabor, null, null,
                codigo, motivo, null, null, null, ahora, ahora);
    }

    /** Anulación que llega antes que el registro: un registro posterior se rechazará con SAGA_ANULADA. */
    public static SagaProcesada anuladaSinRegistro(UUID idSaga, UUID idCampania, UUID idLabor, Instant ahora) {
        return new SagaProcesada(idSaga, ResultadoSagaProcesada.ANULADO, idCampania, idLabor, null, null,
                null, null, ANULACION_APLICADA, true, null, ahora, ahora);
    }

    public void marcarAnulada(Instant ahora) {
        resultado = ResultadoSagaProcesada.ANULADO;
        anulacionResultado = ANULACION_APLICADA;
        anulacionSinEfecto = false;
        fechaActualizacion = ahora;
    }

    public void marcarAnulacionRechazada(String codigoRechazo, Instant ahora) {
        anulacionResultado = ANULACION_RECHAZADA;
        anulacionCodigo = codigoRechazo;
        fechaActualizacion = ahora;
    }

    public void marcarAnulacionSinEfecto(Instant ahora) {
        anulacionResultado = ANULACION_APLICADA;
        anulacionSinEfecto = true;
        fechaActualizacion = ahora;
    }

    public UUID getIdSaga() {
        return idSaga;
    }

    public ResultadoSagaProcesada getResultado() {
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
