package com.agrosystem.gestion.domain.shared;

public class ExcepcionDominio extends RuntimeException {

    public enum Tipo {
        NO_ENCONTRADO,
        CONFLICTO,
        REGLA_NEGOCIO
    }

    private final String codigo;
    private final Tipo tipo;

    public ExcepcionDominio(String codigo, String mensaje, Tipo tipo) {
        super(mensaje);
        this.codigo = codigo;
        this.tipo = tipo;
    }

    public String getCodigo() {
        return codigo;
    }

    public Tipo getTipo() {
        return tipo;
    }
}
