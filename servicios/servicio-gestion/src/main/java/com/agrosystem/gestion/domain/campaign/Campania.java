package com.agrosystem.gestion.domain.campaign;

import com.agrosystem.gestion.domain.crop.UnidadProduccion;
import com.agrosystem.gestion.domain.shared.Dinero;
import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.agrosystem.gestion.domain.shared.Hectareas;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
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
    private final List<CostoCampania> costos;
    private ProduccionCampania produccion;

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
            Instant fechaActualizacion,
            List<CostoCampania> costos,
            ProduccionCampania produccion) {
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
        this.costos = new ArrayList<>(costos);
        this.produccion = produccion;
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
                ahora,
                List.of(),
                null);
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
            Instant fechaActualizacion,
            List<CostoCampania> costos,
            ProduccionCampania produccion) {
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
                fechaActualizacion,
                costos,
                produccion);
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
        rechazarSiFinalizada();
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

    public CostoCampania registrarCostoManual(
            CategoriaCosto categoria,
            Dinero monto,
            LocalDate fecha,
            String descripcion,
            LocalDate hoy,
            Instant ahora) {
        rechazarSiFinalizada();
        CostoCampania costo = CostoCampania.crearManual(categoria, monto, fecha, descripcion, hoy, ahora);
        costos.add(costo);
        fechaActualizacion = ahora;
        return costo;
    }

    public CostoCampania modificarCostoManual(
            UUID idCosto,
            CategoriaCosto categoria,
            Dinero monto,
            LocalDate fecha,
            String descripcion,
            LocalDate hoy,
            Instant ahora) {
        CostoCampania costo = costoEditable(idCosto);
        costo.modificar(categoria, monto, fecha, descripcion, hoy);
        fechaActualizacion = ahora;
        return costo;
    }

    public void eliminarCostoManual(UUID idCosto, Instant ahora) {
        costos.remove(costoEditable(idCosto));
        fechaActualizacion = ahora;
    }

    public CostoCampania registrarCostoSaga(UUID idSaga, UUID idLabor, Dinero monto, LocalDate fecha, Instant ahora) {
        rechazarSiFinalizada();
        CostoCampania costo = CostoCampania.crearSaga(idSaga, idLabor, monto, fecha, ahora);
        costos.add(costo);
        fechaActualizacion = ahora;
        return costo;
    }

    public void anularCostoSaga(UUID idSaga, Instant ahora) {
        rechazarSiFinalizada();
        costos.stream()
                .filter(costo -> idSaga.equals(costo.getIdSaga()))
                .findFirst()
                .orElseThrow(() -> new IllegalStateException("La campaña no tiene un costo de la saga " + idSaga))
                .anular(ahora);
        fechaActualizacion = ahora;
    }

    private CostoCampania costoEditable(UUID idCosto) {
        CostoCampania costo = costos.stream()
                .filter(candidato -> candidato.getId().equals(idCosto))
                .findFirst()
                .orElseThrow(() -> new ExcepcionDominio(
                        "COSTO_NO_ENCONTRADO", "El costo no existe en esta campaña.", ExcepcionDominio.Tipo.NO_ENCONTRADO));
        rechazarSiFinalizada();
        if (!costo.esManual()) {
            throw new ExcepcionDominio(
                    "COSTO_NO_EDITABLE",
                    "Un costo originado por una labor no se modifica ni se elimina.",
                    ExcepcionDominio.Tipo.REGLA_NEGOCIO);
        }
        return costo;
    }

    private void rechazarSiFinalizada() {
        if (estado == EstadoCampania.FINALIZADA) {
            throw new ExcepcionDominio(
                    "CAMPANIA_FINALIZADA",
                    "La campaña está finalizada y no admite cambios.",
                    ExcepcionDominio.Tipo.REGLA_NEGOCIO);
        }
    }

    public Dinero costoTotal() {
        return costosVigentes().stream().map(CostoCampania::getMonto).reduce(Dinero.CERO, Dinero::sumar);
    }

    public int cantidadCostos() {
        return costosVigentes().size();
    }

    public Map<CategoriaCosto, Dinero> subtotalesPorCategoria() {
        Map<CategoriaCosto, Dinero> subtotales = new EnumMap<>(CategoriaCosto.class);
        for (CategoriaCosto categoria : CategoriaCosto.values()) {
            subtotales.put(categoria, Dinero.CERO);
        }
        costosVigentes().forEach(costo -> subtotales.merge(costo.getCategoria(), costo.getMonto(), Dinero::sumar));
        return subtotales;
    }

    private List<CostoCampania> costosVigentes() {
        return costos.stream().filter(costo -> !costo.isAnulado()).toList();
    }

    /** Solo en EN_CURSO; registrar de nuevo reemplaza la anterior (RQ-PRO-02). */
    public ProduccionCampania registrarProduccion(
            BigDecimal cantidad,
            UnidadProduccion unidad,
            LocalDate fechaCosecha,
            String observaciones,
            LocalDate hoy,
            String usuario,
            Instant ahora) {
        rechazarSiFinalizada();
        if (estado != EstadoCampania.EN_CURSO) {
            throw new ExcepcionDominio(
                    "CAMPANIA_NO_EN_CURSO",
                    "La producción solo se registra en una campaña en curso.",
                    ExcepcionDominio.Tipo.REGLA_NEGOCIO);
        }
        LocalDate diaInicioEjecucion = fechaInicioEjecucion.atOffset(ZoneOffset.UTC).toLocalDate();
        produccion = ProduccionCampania.crear(
                cantidad, unidad, fechaCosecha, observaciones, diaInicioEjecucion, hoy, usuario, ahora);
        fechaActualizacion = ahora;
        return produccion;
    }

    public boolean tieneProduccion() {
        return produccion != null;
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

    public List<CostoCampania> getCostos() {
        return Collections.unmodifiableList(costos);
    }

    public ProduccionCampania getProduccion() {
        return produccion;
    }
}
