package com.agrosystem.gestion.interfaces.rest.error;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.stereotype.Component;

/** Responde los errores de la cadena de seguridad con el formato común. */
@Component
public class ManejadorErroresSeguridad implements AuthenticationEntryPoint, AccessDeniedHandler {

    private final ObjectMapper mapeador;

    public ManejadorErroresSeguridad(ObjectMapper mapeador) {
        this.mapeador = mapeador;
    }

    @Override
    public void commence(HttpServletRequest solicitud, HttpServletResponse respuesta, AuthenticationException error)
            throws IOException {
        respuesta.setHeader(HttpHeaders.WWW_AUTHENTICATE, "Bearer");
        escribir(respuesta, HttpServletResponse.SC_UNAUTHORIZED, RespuestaError.de(
                "NO_AUTENTICADO", "Se requiere un token válido."));
    }

    @Override
    public void handle(HttpServletRequest solicitud, HttpServletResponse respuesta, AccessDeniedException error)
            throws IOException {
        escribir(respuesta, HttpServletResponse.SC_FORBIDDEN, RespuestaError.de(
                "SIN_PERMISO", ManejadorGlobalExcepciones.MENSAJE_SIN_PERMISO));
    }

    private void escribir(HttpServletResponse respuesta, int estado, RespuestaError cuerpo) throws IOException {
        respuesta.setStatus(estado);
        respuesta.setContentType(MediaType.APPLICATION_JSON_VALUE);
        respuesta.setCharacterEncoding(StandardCharsets.UTF_8.name());
        mapeador.writeValue(respuesta.getWriter(), cuerpo);
    }
}
