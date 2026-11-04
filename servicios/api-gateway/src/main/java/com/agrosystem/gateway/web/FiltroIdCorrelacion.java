package com.agrosystem.gateway.web;

import java.util.UUID;
import java.util.regex.Pattern;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

/**
 * Conserva o genera el X-Correlation-Id, lo envía al servicio destino y lo devuelve en la respuesta.
 * Corre antes de la seguridad para que los 401 también lo lleven (RNF-22).
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class FiltroIdCorrelacion implements WebFilter {

    public static final String HEADER = "X-Correlation-Id";
    public static final String ATRIBUTO = "idCorrelacion";

    // El mismo formato que aceptan los servicios, o más estricto (spec-enrutamiento.md 1.6)
    private static final Pattern FORMATO_VALIDO = Pattern.compile("[A-Za-z0-9-]{1,64}");

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain cadena) {
        String idCorrelacion = obtenerOGenerar(exchange.getRequest().getHeaders().getFirst(HEADER));
        exchange.getAttributes().put(ATRIBUTO, idCorrelacion);
        exchange.getResponse().getHeaders().set(HEADER, idCorrelacion);
        ServerWebExchange conId = exchange.mutate()
                .request(solicitud -> solicitud.headers(headers -> headers.set(HEADER, idCorrelacion)))
                .build();
        return cadena.filter(conId);
    }

    /** El id de la solicitud en curso; los atributos se comparten entre los decoradores del exchange. */
    public static String de(ServerWebExchange exchange) {
        String id = exchange.getAttribute(ATRIBUTO);
        return id != null ? id : UUID.randomUUID().toString();
    }

    private static String obtenerOGenerar(String recibido) {
        if (recibido != null && FORMATO_VALIDO.matcher(recibido).matches()) {
            return recibido;
        }
        return UUID.randomUUID().toString();
    }
}
