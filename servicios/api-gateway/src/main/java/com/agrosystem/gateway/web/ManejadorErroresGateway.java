package com.agrosystem.gateway.web;

import io.netty.channel.ConnectTimeoutException;
import java.net.ConnectException;
import java.net.UnknownHostException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.web.reactive.error.ErrorWebExceptionHandler;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.AuthenticationServiceException;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/**
 * Traduce los fallos del propio gateway al formato común (spec-enrutamiento.md 2.5).
 * Las respuestas de los servicios, incluidos sus 4xx y 5xx, no pasan por aquí: se devuelven tal cual.
 */
@Component
@Order(-2)
public class ManejadorErroresGateway implements ErrorWebExceptionHandler {

    private static final Logger LOG = LoggerFactory.getLogger(ManejadorErroresGateway.class);

    private final EscritorRespuestaError escritor;

    public ManejadorErroresGateway(EscritorRespuestaError escritor) {
        this.escritor = escritor;
    }

    @Override
    public Mono<Void> handle(ServerWebExchange exchange, Throwable error) {
        if (exchange.getResponse().isCommitted()) {
            // El servicio cortó la respuesta a mitad: ya no se puede escribir un cuerpo
            return Mono.error(error);
        }
        Traduccion traduccion = traducir(error);
        if (traduccion.estado().is5xxServerError()) {
            LOG.atWarn()
                    .addKeyValue("idCorrelacion", FiltroIdCorrelacion.de(exchange))
                    .addKeyValue("codigo", traduccion.codigo().name())
                    .log("Error del gateway: {}", error.toString());
        }
        return escritor.escribir(exchange, traduccion.estado(), traduccion.codigo());
    }

    private static Traduccion traducir(Throwable error) {
        if (error instanceof ResponseStatusException conEstado) {
            int estado = conEstado.getStatusCode().value();
            if (estado == HttpStatus.NOT_FOUND.value()) {
                return new Traduccion(HttpStatus.NOT_FOUND, CodigoError.RUTA_NO_ENCONTRADA);
            }
            if (estado == HttpStatus.GATEWAY_TIMEOUT.value()) {
                return new Traduccion(HttpStatus.GATEWAY_TIMEOUT, CodigoError.TIEMPO_AGOTADO);
            }
            if (estado == HttpStatus.SERVICE_UNAVAILABLE.value() || causadoPorConexion(error)) {
                return new Traduccion(HttpStatus.SERVICE_UNAVAILABLE, CodigoError.SERVICIO_NO_DISPONIBLE);
            }
            if (conEstado.getStatusCode().is4xxClientError()) {
                return new Traduccion(HttpStatus.valueOf(estado), CodigoError.DATOS_INVALIDOS);
            }
        }
        if (causadoPorConexion(error)) {
            return new Traduccion(HttpStatus.SERVICE_UNAVAILABLE, CodigoError.SERVICIO_NO_DISPONIBLE);
        }
        if (error instanceof AuthenticationServiceException) {
            return new Traduccion(HttpStatus.SERVICE_UNAVAILABLE, CodigoError.AUTENTICACION_NO_DISPONIBLE);
        }
        return new Traduccion(HttpStatus.INTERNAL_SERVER_ERROR, CodigoError.ERROR_INTERNO);
    }

    /**
     * Conexión rechazada, sin respuesta al conectar o nombre que no se resuelve. Lo último es lo habitual en
     * Docker Compose: el nombre de un contenedor apagado deja de existir en la red.
     */
    private static boolean causadoPorConexion(Throwable error) {
        for (Throwable actual = error; actual != null; actual = actual.getCause()) {
            if (actual instanceof ConnectException || actual instanceof ConnectTimeoutException
                    || actual instanceof UnknownHostException) {
                return true;
            }
        }
        return false;
    }

    private record Traduccion(HttpStatus estado, CodigoError codigo) {}
}
