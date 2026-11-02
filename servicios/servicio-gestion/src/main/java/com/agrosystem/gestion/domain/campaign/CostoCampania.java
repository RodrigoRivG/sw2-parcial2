package com.agrosystem.gestion.domain.campaign;

import com.agrosystem.gestion.domain.shared.Dinero;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

public class CostoCampania {

    private final UUID id;
    private CategoriaCosto categoria;
    private Dinero monto;
    private LocalDate fecha;
    private String descripcion;
    private final OrigenCosto origen;
    private final UUID idSaga;
    private final UUID idLabor;
    private final boolean anulado;
    private final Instant fechaAnulacion;
    private final Instant fechaRegistro;

    private CostoCampania(
            UUID id,
            CategoriaCosto categoria,
            Dinero monto,
            LocalDate fecha,
            String descripcion,
            OrigenCosto origen,
            UUID idSaga,
            UUID idLabor,
            boolean anulado,
            Instant fechaAnulacion,
            Instant fechaRegistro) {
        this.id = id;
        this.categoria = categoria;
        this.monto = monto;
        this.fecha = fecha;
        this.descripcion = descripcion;
        this.origen = origen;
        this.idSaga = idSaga;
        this.idLabor = idLabor;
        this.anulado = anulado;
        this.fechaAnulacion = fechaAnulacion;
        this.fechaRegistro = fechaRegistro;
    }

    static CostoCampania crearManual(
            CategoriaCosto categoria, Dinero monto, LocalDate fecha, String descripcion, LocalDate hoy, Instant ahora) {
        validar(monto, fecha, hoy);
        return new CostoCampania(
                UUID.randomUUID(),
                categoria,
                monto,
                fecha,
                descripcion.trim(),
                OrigenCosto.MANUAL,
                null,
                null,
                false,
                null,
                ahora);
    }

    /** Reconstruye un costo ya guardado; no vuelve a aplicar reglas de creación. */
    public static CostoCampania reconstruir(
            UUID id,
            CategoriaCosto categoria,
            Dinero monto,
            LocalDate fecha,
            String descripcion,
            OrigenCosto origen,
            UUID idSaga,
            UUID idLabor,
            boolean anulado,
            Instant fechaAnulacion,
            Instant fechaRegistro) {
        return new CostoCampania(
                id, categoria, monto, fecha, descripcion, origen, idSaga, idLabor, anulado, fechaAnulacion, fechaRegistro);
    }

    void modificar(CategoriaCosto categoria, Dinero monto, LocalDate fecha, String descripcion, LocalDate hoy) {
        validar(monto, fecha, hoy);
        this.categoria = categoria;
        this.monto = monto;
        this.fecha = fecha;
        this.descripcion = descripcion.trim();
    }

    private static void validar(Dinero monto, LocalDate fecha, LocalDate hoy) {
        if (!monto.esPositivo()) {
            throw new ExcepcionDominio(
                    "MONTO_INVALIDO", "El monto debe ser mayor a 0.", ExcepcionDominio.Tipo.REGLA_NEGOCIO);
        }
        if (fecha.isAfter(hoy)) {
            throw new ExcepcionDominio(
                    "FECHA_COSTO_INVALIDA",
                    "La fecha del costo no puede ser posterior a hoy.",
                    ExcepcionDominio.Tipo.REGLA_NEGOCIO);
        }
    }

    public boolean esManual() {
        return origen == OrigenCosto.MANUAL;
    }

    public UUID getId() {
        return id;
    }

    public CategoriaCosto getCategoria() {
        return categoria;
    }

    public Dinero getMonto() {
        return monto;
    }

    public LocalDate getFecha() {
        return fecha;
    }

    public String getDescripcion() {
        return descripcion;
    }

    public OrigenCosto getOrigen() {
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
