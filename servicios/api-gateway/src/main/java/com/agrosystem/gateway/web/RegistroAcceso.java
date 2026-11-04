package com.agrosystem.gateway.web;

import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.gateway.route.Route;
import org.springframework.cloud.gateway.support.ServerWebExchangeUtils;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

/**
 * Un log JSON por solicitud (constitución §6). Corre antes de la seguridad para registrar también los 401,
 * y escribe justo antes de enviar la respuesta, cuando el estado ya está fijado (también en los errores,
 * que se resuelven fuera de la cadena de filtros). Nunca registra headers ni el cuerpo.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 1)
public class RegistroAcceso implements WebFilter {

    /** Atributo con el {@code sub} del token; lo guarda {@link FiltroSujeto}, que corre después de la seguridad. */
    public static final String ATRIBUTO_SUB = "subAutenticado";

    private static final Logger LOG = LoggerFactory.getLogger(RegistroAcceso.class);
    private static final String SIN_DESTINO = "ninguno";

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain cadena) {
        long inicio = System.nanoTime();
        exchange.getResponse().beforeCommit(() -> {
            registrar(exchange, (System.nanoTime() - inicio) / 1_000_000);
            return Mono.empty();
        });
        return cadena.filter(exchange);
    }

    private static void registrar(ServerWebExchange exchange, long duracionMs) {
        HttpStatusCode estado = exchange.getResponse().getStatusCode();
        LOG.atInfo()
                .addKeyValue("idCorrelacion", FiltroIdCorrelacion.de(exchange))
                .addKeyValue("metodo", exchange.getRequest().getMethod().name())
                .addKeyValue("ruta", exchange.getRequest().getPath().value())
                .addKeyValue("servicioDestino", servicioDestino(exchange))
                .addKeyValue("estado", estado != null ? estado.value() : 200)
                .addKeyValue("duracionMs", duracionMs)
                .addKeyValue("sub", exchange.getAttributeOrDefault(ATRIBUTO_SUB, ""))
                .log("Solicitud atendida");
    }

    private static String servicioDestino(ServerWebExchange exchange) {
        Route ruta = exchange.getAttribute(ServerWebExchangeUtils.GATEWAY_ROUTE_ATTR);
        if (ruta == null) {
            return SIN_DESTINO;
        }
        Map<String, Object> metadatos = ruta.getMetadata();
        Object servicio = metadatos.get("servicio");
        return servicio != null ? servicio.toString() : ruta.getId();
    }
}
