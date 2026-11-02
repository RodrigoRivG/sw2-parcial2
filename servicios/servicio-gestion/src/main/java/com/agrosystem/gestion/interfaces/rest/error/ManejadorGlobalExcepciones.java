package com.agrosystem.gestion.interfaces.rest.error;

import com.agrosystem.gestion.domain.shared.ExcepcionDominio;
import com.fasterxml.jackson.databind.JsonMappingException;
import java.util.List;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

@RestControllerAdvice
public class ManejadorGlobalExcepciones extends ResponseEntityExceptionHandler {

    static final String MENSAJE_SIN_PERMISO = "No tiene permiso para realizar esta operación.";

    private static final Logger LOG = LoggerFactory.getLogger(ManejadorGlobalExcepciones.class);
    private static final String DATOS_INVALIDOS = "DATOS_INVALIDOS";
    private static final String MENSAJE_DATOS_INVALIDOS = "Los datos enviados no son válidos.";

    @ExceptionHandler(ExcepcionDominio.class)
    public ResponseEntity<RespuestaError> manejarDominio(ExcepcionDominio error) {
        HttpStatus estado = switch (error.getTipo()) {
            case NO_ENCONTRADO -> HttpStatus.NOT_FOUND;
            case CONFLICTO -> HttpStatus.CONFLICT;
            case REGLA_NEGOCIO -> HttpStatus.UNPROCESSABLE_ENTITY;
        };
        return responder(estado, RespuestaError.de(error.getCodigo(), error.getMessage()));
    }

    @ExceptionHandler(ObjectOptimisticLockingFailureException.class)
    public ResponseEntity<RespuestaError> manejarConcurrencia(ObjectOptimisticLockingFailureException error) {
        return responder(HttpStatus.CONFLICT, RespuestaError.de(
                "CONFLICTO_CONCURRENCIA", "El registro cambió desde que se leyó. Vuelva a consultarlo."));
    }

    @ExceptionHandler(SolicitudInvalidaExcepcion.class)
    public ResponseEntity<RespuestaError> manejarSolicitudInvalida(SolicitudInvalidaExcepcion error) {
        return responder(HttpStatus.BAD_REQUEST, RespuestaError.de(
                DATOS_INVALIDOS,
                MENSAJE_DATOS_INVALIDOS,
                List.of(new DetalleError(error.getCampo(), error.getMessage()))));
    }

    /** Sin este manejador, el 403 de @PreAuthorize terminaría como un 500. */
    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<RespuestaError> manejarAccesoDenegado(AccessDeniedException error) {
        return responder(HttpStatus.FORBIDDEN, RespuestaError.de("SIN_PERMISO", MENSAJE_SIN_PERMISO));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<RespuestaError> manejarInesperada(Exception error) {
        LOG.error("Error inesperado", error);
        return responder(HttpStatus.INTERNAL_SERVER_ERROR, errorInterno());
    }

    @Override
    protected ResponseEntity<Object> handleMethodArgumentNotValid(
            MethodArgumentNotValidException error, HttpHeaders headers, HttpStatusCode estado, WebRequest solicitud) {
        List<DetalleError> detalles = error.getBindingResult().getFieldErrors().stream()
                .map(campo -> new DetalleError(campo.getField(), campo.getDefaultMessage()))
                .toList();
        return responderObjeto(headers, estado, RespuestaError.de(DATOS_INVALIDOS, MENSAJE_DATOS_INVALIDOS, detalles));
    }

    @Override
    protected ResponseEntity<Object> handleHttpMessageNotReadable(
            HttpMessageNotReadableException error, HttpHeaders headers, HttpStatusCode estado, WebRequest solicitud) {
        List<DetalleError> detalles = List.of();
        if (error.getCause() instanceof JsonMappingException mapeo && !mapeo.getPath().isEmpty()) {
            String campo = mapeo.getPath().stream()
                    .map(JsonMappingException.Reference::getFieldName)
                    .filter(nombre -> nombre != null)
                    .collect(Collectors.joining("."));
            detalles = List.of(new DetalleError(campo, "El valor o su formato no son válidos."));
        }
        return responderObjeto(headers, estado, RespuestaError.de(DATOS_INVALIDOS, MENSAJE_DATOS_INVALIDOS, detalles));
    }

    /** Traduce al formato común los demás errores de Spring MVC. */
    @Override
    protected ResponseEntity<Object> handleExceptionInternal(
            Exception error, Object cuerpo, HttpHeaders headers, HttpStatusCode estado, WebRequest solicitud) {
        RespuestaError respuesta;
        if (estado.value() == HttpStatus.NOT_FOUND.value()) {
            respuesta = RespuestaError.de("RECURSO_NO_ENCONTRADO", "El recurso solicitado no existe.");
        } else if (estado.value() == HttpStatus.METHOD_NOT_ALLOWED.value()) {
            respuesta = RespuestaError.de("METODO_NO_PERMITIDO", "El método no está permitido en esta ruta.");
        } else if (estado.is4xxClientError()) {
            respuesta = RespuestaError.de(DATOS_INVALIDOS, MENSAJE_DATOS_INVALIDOS);
        } else {
            LOG.error("Error inesperado", error);
            respuesta = errorInterno();
        }
        return responderObjeto(headers, estado, respuesta);
    }

    private RespuestaError errorInterno() {
        return RespuestaError.de("ERROR_INTERNO", "Ocurrió un error inesperado. Intente de nuevo más tarde.");
    }

    private ResponseEntity<RespuestaError> responder(HttpStatus estado, RespuestaError cuerpo) {
        return ResponseEntity.status(estado).contentType(MediaType.APPLICATION_JSON).body(cuerpo);
    }

    private ResponseEntity<Object> responderObjeto(HttpHeaders headers, HttpStatusCode estado, RespuestaError cuerpo) {
        return ResponseEntity.status(estado)
                .headers(headers)
                .contentType(MediaType.APPLICATION_JSON)
                .body(cuerpo);
    }
}
