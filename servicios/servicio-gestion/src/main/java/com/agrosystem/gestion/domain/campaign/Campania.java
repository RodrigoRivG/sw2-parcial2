package com.agrosystem.gestion.domain.campaign;

import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.agrosystem.gestion.domain.shared.Hectareas;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

public class Campania {

    private final UUID id;
    private String nombre;
    private UUID idParcela;
    private UUID idCultivo;
    private LocalDate fechaInicio;
    private LocalDate fechaFin;
    private Hectareas superficie;
    private EstadoCampania estado;
    private Instant fechaInicioEjecucion;
    private Instant fechaFinalizacion;
    private final Long version;
    private final Instant fechaCreacion;
    private Instant fechaActualizacion;

    private Campania(
            UUID id,
            String nombre,
            UUID idParcela,
            UUID idCultivo,
            LocalDate fechaInicio,
            LocalDate fechaFin,
            Hectareas superficie,
            EstadoCampania estado,
            Instant fechaInicioEjecucion,
            Instant fechaFinalizacion,
            Long version,
            Instant fechaCreacion,
            Instant fechaActualizacion) {
        this.id = id;
        this.nombre = nombre;
        this.idParcela = idParcela;
        this.idCultivo = idCultivo;
        this.fechaInicio = fechaInicio;
        this.fechaFin = fechaFin;
        this.superficie = superficie;
        this.estado = estado;
        this.fechaInicioEjecucion = fechaInicioEjecucion;
        this.fechaFinalizacion = fechaFinalizacion;
        this.version = version;
        this.fechaCreacion = fechaCreacion;
        this.fechaActualizacion = fechaActualizacion;
    }

    public static Campania crear(
            String nombre,
            UUID idParcela,
            UUID idCultivo,
            LocalDate fechaInicio,
            LocalDate fechaFin,
            Hectareas superficie,
            Instant ahora) {
        validarFechas(fechaInicio, fechaFin);
        return new Campania(
                UUID.randomUUID(),
                nombre.trim(),
                idParcela,
                idCultivo,
                fechaInicio,
                fechaFin,
                superficie,
                EstadoCampania.PLANIFICADA,
                null,
                null,
                null,
                ahora,
                ahora);
    }

    /** Reconstruye una campaña ya guardada; no vuelve a aplicar reglas de creación. */
    public static Campania reconstruir(
            UUID id,
            String nombre,
            UUID idParcela,
            UUID idCultivo,
            LocalDate fechaInicio,
            LocalDate fechaFin,
            Hectareas superficie,
            EstadoCampania estado,
            Instant fechaInicioEjecucion,
            Instant fechaFinalizacion,
            Long version,
            Instant fechaCreacion,
            Instant fechaActualizacion) {
        return new Campania(
                id,
                nombre,
                idParcela,
                idCultivo,
                fechaInicio,
                fechaFin,
                superficie,
                estado,
                fechaInicioEjecucion,
                fechaFinalizacion,
                version,
                fechaCreacion,
                fechaActualizacion);
    }

    /** Aplica la tabla de campos modificables por estado (RQ-CAM-08). */
    public void actualizarDatos(
            String nombre,
            UUID idParcela,
            UUID idCultivo,
            LocalDate fechaInicio,
            LocalDate fechaFin,
            Hectareas superficie,
            Instant ahora) {
        if (estado == EstadoCampania.FINALIZADA) {
            throw new ExcepcionDominio(
                    "CAMPANIA_FINALIZADA",
                    "La campaña está finalizada y no admite cambios.",
                    ExcepcionDominio.Tipo.REGLA_NEGOCIO);
        }
        if (estado == EstadoCampania.EN_CURSO
                && (!idParcela.equals(this.idParcela)
                        || !idCultivo.equals(this.idCultivo)
                        || !fechaInicio.equals(this.fechaInicio))) {
            throw new ExcepcionDominio(
                    "CAMPO_NO_MODIFICABLE",
                    "La parcela, el cultivo y la fecha de inicio no se modifican en una campaña en curso.",
                    ExcepcionDominio.Tipo.REGLA_NEGOCIO);
        }
        validarFechas(fechaInicio, fechaFin);
        this.nombre = nombre.trim();
        this.idParcela = idParcela;
        this.idCultivo = idCultivo;
        this.fechaInicio = fechaInicio;
        this.fechaFin = fechaFin;
        this.superficie = superficie;
        this.fechaActualizacion = ahora;
    }

    /** Solo PLANIFICADA → EN_CURSO → FINALIZADA; no se retrocede (RN-02). */
    public void cambiarEstado(EstadoCampania destino, Instant ahora) {
        if (estado == EstadoCampania.PLANIFICADA && destino == EstadoCampania.EN_CURSO) {
            fechaInicioEjecucion = ahora;
        } else if (estado == EstadoCampania.EN_CURSO && destino == EstadoCampania.FINALIZADA) {
            if (!tieneProduccion()) {
                throw new ExcepcionDominio(
                        "FINALIZACION_SIN_PRODUCCION",
                        "La campaña no se puede finalizar sin producción registrada.",
                        ExcepcionDominio.Tipo.REGLA_NEGOCIO);
            }
            fechaFinalizacion = ahora;
        } else {
            throw new ExcepcionDominio(
                    "TRANSICION_ESTADO_INVALIDA",
                    "La campaña no puede pasar de " + estado + " a " + destino + ".",
                    ExcepcionDominio.Tipo.REGLA_NEGOCIO);
        }
        estado = destino;
        fechaActualizacion = ahora;
    }

    /** La producción se agrega con spec-produccion.md; hasta entonces ninguna campaña la tiene. */
    public boolean tieneProduccion() {
        return false;
    }

    private static void validarFechas(LocalDate fechaInicio, LocalDate fechaFin) {
        if (!fechaFin.isAfter(fechaInicio)) {
            throw new ExcepcionDominio(
                    "FECHAS_INVALIDAS",
                    "La fecha de fin debe ser posterior a la de inicio.",
                    ExcepcionDominio.Tipo.REGLA_NEGOCIO);
        }
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

    public Hectareas getSuperficie() {
        return superficie;
    }

    public EstadoCampania getEstado() {
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
