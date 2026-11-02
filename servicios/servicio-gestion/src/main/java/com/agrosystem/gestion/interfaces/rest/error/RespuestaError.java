package com.agrosystem.gestion.interfaces.rest.error;

import com.agrosystem.gestion.interfaces.rest.FiltroIdCorrelacion;
import java.util.List;
import org.slf4j.MDC;

public record RespuestaError(String codigo, String mensaje, List<DetalleError> detalles, String idCorrelacion) {

    public static RespuestaError de(String codigo, String mensaje) {
        return de(codigo, mensaje, List.of());
    }

    public static RespuestaError de(String codigo, String mensaje, List<DetalleError> detalles) {
        return new RespuestaError(codigo, mensaje, detalles, MDC.get(FiltroIdCorrelacion.CLAVE_MDC));
    }
}
