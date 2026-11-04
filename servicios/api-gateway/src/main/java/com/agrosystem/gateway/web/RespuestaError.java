package com.agrosystem.gateway.web;

import java.util.List;

/** Formato común de error de los microservicios (constitución §6). */
public record RespuestaError(String codigo, String mensaje, List<Object> detalles, String idCorrelacion) {

    public static RespuestaError de(String codigo, String mensaje, String idCorrelacion) {
        return new RespuestaError(codigo, mensaje, List.of(), idCorrelacion);
    }
}
