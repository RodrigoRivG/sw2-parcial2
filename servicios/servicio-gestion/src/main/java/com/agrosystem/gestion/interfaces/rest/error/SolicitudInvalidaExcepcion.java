package com.agrosystem.gestion.interfaces.rest.error;

public class SolicitudInvalidaExcepcion extends RuntimeException {

    private final String campo;

    public SolicitudInvalidaExcepcion(String campo, String mensaje) {
        super(mensaje);
        this.campo = campo;
    }

    public String getCampo() {
        return campo;
    }
}
