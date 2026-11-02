package com.agrosystem.gestion.domain.plot;

import com.agrosystem.gestion.domain.shared.Hectareas;
import java.time.Instant;
import java.util.UUID;

public class Parcela {

    private final UUID id;
    private String nombre;
    private Hectareas superficie;
    private String ubicacion;
    private String descripcion;
    private final Long version;
    private final Instant fechaCreacion;
    private Instant fechaActualizacion;

    private Parcela(
            UUID id,
            String nombre,
            Hectareas superficie,
            String ubicacion,
            String descripcion,
            Long version,
            Instant fechaCreacion,
            Instant fechaActualizacion) {
        this.id = id;
        this.nombre = nombre;
        this.superficie = superficie;
        this.ubicacion = ubicacion;
        this.descripcion = descripcion;
        this.version = version;
        this.fechaCreacion = fechaCreacion;
        this.fechaActualizacion = fechaActualizacion;
    }

    public static Parcela crear(String nombre, Hectareas superficie, String ubicacion, String descripcion, Instant ahora) {
        return new Parcela(
                UUID.randomUUID(),
                nombre.trim(),
                superficie,
                recortarOpcional(ubicacion),
                recortarOpcional(descripcion),
                null,
                ahora,
                ahora);
    }

    /** Reconstruye una parcela ya guardada; no vuelve a aplicar reglas de creación. */
    public static Parcela reconstruir(
            UUID id,
            String nombre,
            Hectareas superficie,
            String ubicacion,
            String descripcion,
            Long version,
            Instant fechaCreacion,
            Instant fechaActualizacion) {
        return new Parcela(id, nombre, superficie, ubicacion, descripcion, version, fechaCreacion, fechaActualizacion);
    }

    public void actualizar(String nombre, Hectareas superficie, String ubicacion, String descripcion, Instant ahora) {
        this.nombre = nombre.trim();
        this.superficie = superficie;
        this.ubicacion = recortarOpcional(ubicacion);
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

    public Hectareas getSuperficie() {
        return superficie;
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
