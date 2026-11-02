package com.agrosystem.gestion.interfaces.rest;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.UUID;
import java.util.regex.Pattern;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/** Se ejecuta antes de la cadena de seguridad para que los errores 401 y 403 también lleven el ID. */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class FiltroIdCorrelacion extends OncePerRequestFilter {

    public static final String HEADER = "X-Correlation-Id";
    public static final String CLAVE_MDC = "idCorrelacion";

    private static final Pattern FORMATO_VALIDO = Pattern.compile("[A-Za-z0-9-]{1,64}");

    @Override
    protected void doFilterInternal(HttpServletRequest solicitud, HttpServletResponse respuesta, FilterChain cadena)
            throws ServletException, IOException {
        String idCorrelacion = obtenerOGenerar(solicitud.getHeader(HEADER));
        MDC.put(CLAVE_MDC, idCorrelacion);
        respuesta.setHeader(HEADER, idCorrelacion);
        try {
            cadena.doFilter(solicitud, respuesta);
        } finally {
            MDC.remove(CLAVE_MDC);
        }
    }

    private String obtenerOGenerar(String recibido) {
        if (recibido != null && FORMATO_VALIDO.matcher(recibido).matches()) {
            return recibido;
        }
        return UUID.randomUUID().toString();
    }
}
