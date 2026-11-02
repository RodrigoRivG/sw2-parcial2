package com.agrosystem.gestion.domain.crop;

import java.time.Instant;
import java.util.UUID;

public class Cultivo {

    private final UUID id;
    private String nombre;
    private String variedad;
    private final UnidadProduccion unidadMedida;
    private String descripcion;
    private final Long version;
    private final Instant fechaCreacion;
    private Instant fechaActualizacion;

    private Cultivo(
            UUID id,
            String nombre,
            String variedad,
            UnidadProduccion unidadMedida,
            String descripcion,
            Long version,
            Instant fechaCreacion,
            Instant fechaActualizacion) {
        this.id = id;
        this.nombre = nombre;
        this.variedad = variedad;
        this.unidadMedida = unidadMedida;
        this.descripcion = descripcion;
        this.version = version;
        this.fechaCreacion = fechaCreacion;
        this.fechaActualizacion = fechaActualizacion;
    }

    public static Cultivo crear(
            String nombre, String variedad, UnidadProduccion unidadMedida, String descripcion, Instant ahora) {
        return new Cultivo(
                UUID.randomUUID(),
                nombre.trim(),
                recortarOpcional(variedad),
                unidadMedida,
                recortarOpcional(descripcion),
                null,
                ahora,
                ahora);
    }

    /** Reconstruye un cultivo ya guardado; no vuelve a aplicar reglas de creación. */
    public static Cultivo reconstruir(
            UUID id,
            String nombre,
            String variedad,
            UnidadProduccion unidadMedida,
            String descripcion,
            Long version,
            Instant fechaCreacion,
            Instant fechaActualizacion) {
        return new Cultivo(
                id, nombre, variedad, unidadMedida, descripcion, version, fechaCreacion, fechaActualizacion);
    }

    /** La unidad de medida no cambia: KILOGRAMO es su único valor (README D-03). */
    public void actualizar(String nombre, String variedad, String descripcion, Instant ahora) {
        this.nombre = nombre.trim();
        this.variedad = recortarOpcional(variedad);
        this.descripcion = recortarOpcional(descripcion);
        this.fechaActualizacion = ahora;
    }

    private static String recortarOpcional(String texto) {
        if (texto == null || texto.isBlank()) {
            return null;
        }
        return texto.trim();
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

    public UnidadProduccion getUnidadMedida() {
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
